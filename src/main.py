"""FastAPI app — hospital-impact defense platform."""
from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core import schema, store as S
from src.detection import engine as DE, correlate as CO
from src.impact import graph as IG, scoring as IS, explain as IE
from src.response import playbooks as RP, approvals as RA, audit as AU

# init
S.init_db()
MODEL = IG.load_model()
RULES_CFG = {}
import yaml
with open("data/rules.yaml") as f:
    RULES_CFG = yaml.safe_load(f).get("rules", {})
GRAPH = IG.build_graph(MODEL)

app = FastAPI(title="Hospital Impact Defense", version="0.1.0")
app.mount("/static", StaticFiles(directory="public"), name="static")


# ---------- helpers ----------
def get_endpoint_class(ep_id: str) -> str:
    return (MODEL.get("endpoints", {}).get(ep_id, {}) or {}).get("class", "workstation")


def get_rules_for_ep(ep_id: str) -> list[str]:
    ep = (MODEL.get("endpoints", {}).get(ep_id, {}) or {})
    ep_class = ep.get("class", "workstation")
    rules = []
    if ep_class in ("workstation", "server"):
        rules += ["R1", "R2", "R3", "R5", "R6"]
    if ep_class in ("device", "iot"):
        rules += ["R9", "R10"]
    return rules


# ---------- API routes ----------
@app.post("/api/events")
async def ingest_event(ev: schema.Event):
    # store raw event
    S.insert_event(S.DB_PATH, ev.model_dump())
    # run detection on recent events for this endpoint
    events = S.fetch_events(S.DB_PATH, ev.endpoint_id, limit=2000)
    alerts = DE.run_all_rules(ev.endpoint_id, events, RULES_CFG)
    for a in alerts:
        a["id"] = S.new_id("alt")
        a["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        S.insert_alert(S.DB_PATH, a)
        AU.append(S.DB_PATH, "detector", f"alert:{a['rule_id']}", ev.endpoint_id, a)
    # check if we should create/update incident
    recent_alerts = [a for a in S.fetch_alerts(S.DB_PATH, ev.endpoint_id)
                     if a["rule_id"] in [al["rule_id"] for al in alerts]]
    if recent_alerts:
        # correlate alerts for this endpoint
        all_alerts_ep = S.fetch_alerts(S.DB_PATH, ev.endpoint_id)
        corr = CO.correlate(ev.endpoint_id, all_alerts_ep, RULES_CFG)
        # impact
        direct_paths = IG.paths_to_services(GRAPH, ev.endpoint_id)
        lateral_svcs = IG.lateral_reachable_services(GRAPH, MODEL, ev.endpoint_id)
        risk, svc_details = IS.score_incident(direct_paths, lateral_svcs, MODEL, corr["confidence"])
        explanation = IE.explain_incident(ev.endpoint_id, corr["rule_ids"], corr["confidence"], svc_details, ev.endpoint_class)
        # DEDUP: reuse the single open incident per endpoint, update in place
        existing = [i for i in S.fetch_incidents(S.DB_PATH)
                    if i["endpoint_id"] == ev.endpoint_id and i.get("status") == "open"]
        if existing:
            inc_id = existing[0]["id"]
            created = existing[0]["created_at"]
        else:
            inc_id = S.new_id("inc")
            created = corr["created_at"]
        incident = {
            "id": inc_id,
            "endpoint_id": ev.endpoint_id,
            "created_at": created,
            "updated_at": corr["updated_at"],
            "rule_ids": corr["rule_ids"],
            "alert_count": corr["alert_count"],
            "confidence": corr["confidence"],
            "risk_score": risk,
            "services_at_risk": svc_details,
            "paths": [p for _, p in direct_paths],
            "explanation": explanation,
            "status": "open",
        }
        S.upsert_incident(S.DB_PATH, incident)
        # auto-request recommended action once (approval queue)
        ep_class = get_endpoint_class(ev.endpoint_id)
        top_tier = svc_details[0].get("tier") if svc_details else None
        rec = RP.recommend(top_tier, ep_class, risk)
        if not rec.get("auto"):
            pending = [a for a in RA.list_actions(S.DB_PATH, inc_id)
                       if a["action"] == rec["action"] and a["status"] == "pending"]
            if not pending:
                RA.request_action(S.DB_PATH, inc_id, rec["action"],
                                  f"tier-{top_tier}", rec["text"])
        AU.append(S.DB_PATH, "correlator", "incident_upsert", inc_id,
                  {"rules": corr["rule_ids"], "risk": risk})
    return {"ok": True, "alerts_generated": len(alerts)}


@app.get("/api/incidents")
def list_incidents(status: str = "open"):
    incs = S.fetch_incidents(S.DB_PATH)
    if status != "all":
        incs = [i for i in incs if i.get("status", "open") == status]
    # add recommended action
    for inc in incs:
        top_tier = None
        if inc.get("services_at_risk"):
            top_tier = inc["services_at_risk"][0].get("tier")
        ep_class = get_endpoint_class(inc["endpoint_id"])
        inc["recommendation"] = RP.recommend(top_tier, ep_class, inc.get("risk_score", 0))
    return incs


@app.get("/api/incidents/{inc_id}")
def get_incident(inc_id: str):
    inc = S.fetch_incident(S.DB_PATH, inc_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    ep_class = get_endpoint_class(inc["endpoint_id"])
    if inc.get("services_at_risk"):
        top_tier = inc["services_at_risk"][0].get("tier")
        inc["recommendation"] = RP.recommend(top_tier, ep_class, inc.get("risk_score", 0))
    # actions + raw signals for this incident (one row per rule — alerts
    # re-fire on every subsequent event while the rogue condition persists)
    seen: set[str] = set()
    sigs = []
    for a in S.fetch_alerts(S.DB_PATH, inc["endpoint_id"]):
        if a["rule_id"] not in seen:
            seen.add(a["rule_id"])
            sigs.append(a)
    inc["actions"] = RA.list_actions(S.DB_PATH, inc_id)
    inc["alerts"] = sigs
    return inc


class ApproveReq(BaseModel):
    approver: str = "analyst"
    reason: str = ""


def _set_incident_status(inc_id: str, status: str) -> dict | None:
    inc = S.fetch_incident(S.DB_PATH, inc_id)
    if not inc:
        return None
    inc["status"] = status
    inc["updated_at"] = S.now_iso()
    S.upsert_incident(S.DB_PATH, inc)
    return inc


@app.post("/api/incidents/{inc_id}/actions/{action}/approve")
def approve_action(inc_id: str, action: str, req: ApproveReq):
    # find the pending action (matched by action NAME, e.g. isolate_host_pending_approval)
    acts = RA.list_actions(S.DB_PATH, inc_id)
    act = next((a for a in acts if a["action"] == action and a["status"] == "pending"), None)
    if not act:
        raise HTTPException(404, f"No pending '{action}' action on {inc_id}")
    RA.decide(S.DB_PATH, act["id"], True, req.approver)
    AU.append(S.DB_PATH, req.approver, f"action:approve:{action}", inc_id, {"action_id": act["id"]})
    # the human decision is what contains the endpoint: flip incident state + audit it
    _set_incident_status(inc_id, "contained")
    AU.append(S.DB_PATH, req.approver, "incident_contained", inc_id,
              {"via_action": action, "action_id": act["id"]})
    return {"ok": True, "action_id": act["id"], "status": "approved", "incident_status": "contained"}


@app.post("/api/incidents/{inc_id}/actions/{action}/deny")
def deny_action(inc_id: str, action: str, req: ApproveReq):
    acts = RA.list_actions(S.DB_PATH, inc_id)
    act = next((a for a in acts if a["action"] == action and a["status"] == "pending"), None)
    if not act:
        raise HTTPException(404, f"No pending '{action}' action on {inc_id}")
    RA.decide(S.DB_PATH, act["id"], False, req.approver)
    AU.append(S.DB_PATH, req.approver, f"action:deny:{action}", inc_id, {"action_id": act["id"], "reason": req.reason})
    # denied: endpoint stays live, incident stays open for re-review
    return {"ok": True, "action_id": act["id"], "status": "denied", "incident_status": "open"}


@app.get("/api/graph")
def get_graph(highlight_inc: str | None = None):
    highlight: dict = {}
    reach: list[tuple[str, str]] = []
    if highlight_inc:
        inc = S.fetch_incident(S.DB_PATH, highlight_inc)
        if inc:
            highlight[highlight_inc] = inc.get("paths", [])
            ep = inc.get("endpoint_id", "")
            reach = [(ep, s) for s in IG.lateral_reachable_services(GRAPH, MODEL, ep)]
    return IG.graph_json(GRAPH, highlight, reach)


@app.post("/api/sim/start")
async def start_sim(scenario: str = "a"):
    # async spawn
    import asyncio
    asyncio.create_task(run_sim_async(scenario))
    return {"ok": True, "scenario": scenario}


async def run_sim_async(scenario: str):
    events = []
    path = os.path.join("data/scenarios", f"{scenario}.json")
    if not os.path.exists(path):
        for f in os.listdir("data/scenarios"):
            if f.startswith(scenario):
                path = os.path.join("data/scenarios", f)
                break
    with open(path) as f:
        events = json.load(f)
    for ev in events:
        try:
            await ingest_event(schema.Event(**ev))
        except Exception:
            pass
        await asyncio.sleep(0.05)


@app.post("/api/sim/reset")
def reset_sim():
    S.reset_db(S.DB_PATH)
    AU.append(S.DB_PATH, "simulator", "reset", "system", {})
    return {"ok": True}


@app.post("/api/sim/background")
async def start_background(minutes: int = 15, seed: int = 7):
    """Fill the hospital with normal traffic so the dashboard feels alive. Quiet by design."""
    import asyncio
    from src.simulator import background as BG
    events = BG.generate(minutes=minutes, seed=seed)

    async def _emit():
        for ev in events:
            try:
                await ingest_event(schema.Event(**ev))
            except Exception:
                pass
            await asyncio.sleep(0.01)

    asyncio.create_task(_emit())
    return {"ok": True, "events": len(events), "minutes": minutes}


def _service_health() -> list[dict]:
    incs = [i for i in S.fetch_incidents(S.DB_PATH) if i.get("status") == "open"]
    best: dict[str, float] = {}
    for inc in incs:
        for s in inc.get("services_at_risk", []):
            # service risk is stored 0-1; scale to the 0-100 incident scale
            best[s["service"]] = max(best.get(s["service"], 0.0), float(s.get("risk", 0)) * 100)
    out = []
    for svc, sdef in (MODEL.get("services", {}) or {}).items():
        r = best.get(svc, 0.0)
        status = "operational" if r <= 0 else ("watch" if r < 15 else ("degraded" if r < 30 else "critical"))
        out.append({"service": svc, "tier": sdef.get("tier", 3), "status": status,
                    "max_risk": round(r, 1),
                    "fallback": (sdef.get("fallback", {}) or {}).get("name", ""),
                    "max_downtime_min": sdef.get("max_downtime_min", 60)})
    return sorted(out, key=lambda s: s["tier"])


@app.get("/api/stats")
def get_stats():
    latest = S.max_event_ts(S.DB_PATH)
    recent = 0
    if latest:
        try:
            from datetime import datetime, timedelta
            since = (datetime.fromisoformat(latest.replace("Z", "+00:00")) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            recent = S.count_events(S.DB_PATH, since)
        except Exception:
            recent = 0
    open_incs = [i for i in S.fetch_incidents(S.DB_PATH) if i.get("status") == "open"]
    all_incs = S.fetch_incidents(S.DB_PATH)
    open_eps = {i["endpoint_id"] for i in open_incs}
    contained_eps = {i["endpoint_id"] for i in all_incs if i.get("status") == "contained"} - open_eps
    alert_eps = {a["endpoint_id"] for a in S.fetch_alerts(S.DB_PATH)} if open_incs else set()
    ep_status = {}
    for ep in MODEL.get("endpoints", {}):
        if ep in open_eps:
            ep_status[ep] = "compromised"
        elif ep in contained_eps:
            ep_status[ep] = "contained"
        elif ep in alert_eps:
            ep_status[ep] = "watch"
        else:
            ep_status[ep] = "operational"
    return {"endpoints_monitored": len(MODEL.get("endpoints", {})),
            "events_total": S.count_events(S.DB_PATH),
            "events_last_5m": recent,
            "alerts_total": S.count_alerts(S.DB_PATH),
            "alert_ts": S.recent_alert_ts(S.DB_PATH),
            "incidents_open": len(open_incs),
            "max_risk": max([float(i.get("risk_score", 0)) for i in open_incs] or [0.0]),
            "endpoint_status": ep_status,
            "services": _service_health()}


def _event_summary(ev: dict) -> str:
    d = ev.get("details", {}) or {}
    et = ev.get("event_type", "")
    if et == "file_rename":
        return f"{d.get('old_path', '?')} → {d.get('new_path', '?')}"
    if et == "file_modify":
        return str(d.get("path", "?"))
    if et == "process_start":
        return str(d.get("commandline", d.get("process", "?")))[:90]
    if et in ("logon", "auth"):
        return f"{ev.get('user')} {d.get('result', '')} {d.get('logon_type', '')} from {d.get('src_ip', d.get('source_ip', 'local'))}"
    if et == "net_flow":
        return f"{d.get('src_ip', '?')} → {d.get('dst_ip', '?')}:{d.get('dst_port', '?')}/{d.get('proto', '')} ({d.get('bytes', 0)}B)"
    if et == "device_command":
        return f"{d.get('command', '?')} {d.get('param', '')} from {d.get('src_ip', d.get('from', '?'))}"
    if et == "backup_job":
        return f"{d.get('job', '')}: {d.get('action', '')}"
    if et == "agent_heartbeat":
        return f"agent {d.get('status', '')} v{d.get('version', '')}"
    return (d.get("note") or et)[:90]


@app.get("/api/events/recent")
def recent_events(limit: int = 30):
    evs = S.fetch_events(S.DB_PATH, None, limit=min(limit, 100))
    hot_eps = {i["endpoint_id"] for i in S.fetch_incidents(S.DB_PATH) if i.get("status") == "open"}
    return [{"ts": e["ts"], "endpoint_id": e["endpoint_id"], "event_type": e["event_type"],
             "user": e.get("user", ""), "summary": _event_summary(e),
             "note": (e.get("details", {}) or {}).get("note", ""),
             "hot": e["endpoint_id"] in hot_eps} for e in evs]


@app.get("/api/audit")
def get_audit(limit: int = 200):
    return AU.fetch(S.DB_PATH, limit)


@app.get("/api/audit/verify")
def verify_audit():
    return AU.verify(S.DB_PATH)


class TamperNote(BaseModel):
    seq: int | None = None


@app.post("/api/audit/tamper")
def tamper_audit_demo(note: TamperNote | None = None):
    """DEMO ONLY — simulates an attacker editing the audit store, so the panel's
    TAMPER button can show verification failing live. Never expose in production."""
    import sqlite3
    conn = sqlite3.connect(S.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT seq FROM audit ORDER BY seq").fetchall()
    if len(rows) < 1:
        conn.close()
        raise HTTPException(400, "Ledger empty — run a scenario first")
    seq = (note.seq if note and note.seq else (rows[1]["seq"] if len(rows) > 1 else rows[0]["seq"]))
    conn.execute("UPDATE audit SET payload = payload || ' [ALTERED]' WHERE seq = ?", (seq,))
    conn.commit()
    conn.close()
    return {"ok": True, "tampered_seq": seq}


# ---------- UI ----------
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("public/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))