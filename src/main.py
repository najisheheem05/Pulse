"""FastAPI app — hospital-impact defense platform."""
from __future__ import annotations
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
def list_incidents():
    incs = S.fetch_incidents(S.DB_PATH)
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
    # actions for this incident
    inc["actions"] = RA.list_actions(S.DB_PATH, inc_id)
    return inc


class ApproveReq(BaseModel):
    approver: str = "analyst"
    reason: str = ""


@app.post("/api/incidents/{inc_id}/actions/{action}/approve")
def approve_action(inc_id: str, action: str, req: ApproveReq):
    # find the pending action
    acts = RA.list_actions(S.DB_PATH, inc_id)
    act = next((a for a in acts if a["action"] == action and a["status"] == "pending"), None)
    if not act:
        raise HTTPException(404, "No pending action found")
    RA.decide(S.DB_PATH, act["id"], True, req.approver)
    AU.append(S.DB_PATH, req.approver, f"action:approve:{action}", inc_id, {"action_id": act["id"]})
    return {"ok": True, "action_id": act["id"], "status": "approved"}


@app.post("/api/incidents/{inc_id}/actions/{action}/deny")
def deny_action(inc_id: str, action: str, req: ApproveReq):
    acts = RA.list_actions(S.DB_PATH, inc_id)
    act = next((a for a in acts if a["action"] == action and a["status"] == "pending"), None)
    if not act:
        raise HTTPException(404, "No pending action found")
    RA.decide(S.DB_PATH, act["id"], False, req.approver)
    AU.append(S.DB_PATH, req.approver, f"action:deny:{action}", inc_id, {"action_id": act["id"], "reason": req.reason})
    return {"ok": True, "action_id": act["id"], "status": "denied"}


@app.get("/api/graph")
def get_graph(highlight_inc: str | None = None):
    highlight = {}
    if highlight_inc:
        inc = S.fetch_incident(S.DB_PATH, highlight_inc)
        if inc:
            highlight[highlight_inc] = inc.get("paths", [])
    return IG.graph_json(GRAPH, highlight)


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


@app.get("/api/audit")
def get_audit(limit: int = 200):
    return AU.fetch(S.DB_PATH, limit)


@app.get("/api/audit/verify")
def verify_audit():
    return AU.verify(S.DB_PATH)


# ---------- UI ----------
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("public/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))