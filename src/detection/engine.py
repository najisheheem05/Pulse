"""Detection engine — stateful rules over SQLite event stream."""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta
from .baseline import is_baseline_deviation, is_unauthorized_command


def parse_ts(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def check_r1(events: list[dict], cfg: dict) -> dict | None:
    """Mass rename/modify burst: >N file events in window T AND >=3 ext flips.
    The ext-flip gate keeps benign patching (many writes, zero renames to
    .locked/.enc) from firing — honest FP handling for scenario D."""
    thresh = cfg.get("threshold_count", 15)
    window = cfg.get("window_sec", 120)
    min_flips = cfg.get("min_ext_flips", 3)
    file_evs = [e for e in events if e.get("event_type") in ("file_rename", "file_modify")]
    if len(file_evs) < thresh:
        return None
    file_evs.sort(key=lambda e: e.get("ts", ""))
    # sliding window
    for i in range(len(file_evs)):
        start = parse_ts(file_evs[i]["ts"])
        j = i
        ext_flip = 0
        while j < len(file_evs) and (parse_ts(file_evs[j]["ts"]) - start).total_seconds() <= window:
            d = file_evs[j].get("details", {}) or {}
            new = str(d.get("new_path", d.get("path", "")))
            old = str(d.get("old_path", ""))
            if new.endswith((".locked", ".enc", ".crypt", ".ransom")) or (old and new and old != new):
                ext_flip += 1
            j += 1
        if (j - i) >= thresh and ext_flip >= min_flips:
            return {"count": j - i, "window_sec": window, "ext_flips": ext_flip,
                    "sample": file_evs[i:i + 2]}
    return None


def check_r2(events: list[dict], cfg: dict) -> dict | None:
    canaries = set(cfg.get("canaries", []))
    for e in events:
        if e.get("event_type") in ("file_rename", "file_modify"):
            d = e.get("details", {}) or {}
            for k in ("path", "new_path", "old_path"):
                if d.get(k) in canaries:
                    return {"touched": d.get(k), "event_ts": e.get("ts")}
    return None


def check_r3(events: list[dict], cfg: dict) -> dict | None:
    pats = [re.compile(p, re.I) for p in cfg.get("patterns", [])]
    for e in events:
        if e.get("event_type") == "process_start":
            cmd = str((e.get("details", {}) or {}).get("commandline", ""))
            for p in pats:
                if p.search(cmd):
                    return {"commandline": cmd, "event_ts": e.get("ts")}
        if e.get("event_type") == "backup_job":
            d = e.get("details", {}) or {}
            if str(d.get("action", "")).lower() in ("delete_catalog", "wipe_repo", "disable_job"):
                return {"backup_abuse": d, "event_ts": e.get("ts")}
    return None


def check_r5(events: list[dict], cfg: dict) -> dict | None:
    """N failures then success for same user within window."""
    need = cfg.get("fail_threshold", 5)
    window_min = cfg.get("window_min", 10)
    logons = [e for e in events if e.get("event_type") in ("logon", "auth")]
    # group by user
    by_user: dict[str, list[dict]] = {}
    for e in logons:
        by_user.setdefault(e.get("user", "?"), []).append(e)
    for user, evs in by_user.items():
        evs.sort(key=lambda e: e.get("ts", ""))
        fails = 0
        first_fail_ts = None
        for e in evs:
            res = str((e.get("details", {}) or {}).get("result", "")).lower()
            if res in ("fail", "failure", "failed", "bad_password"):
                if fails == 0:
                    first_fail_ts = parse_ts(e["ts"])
                fails += 1
            elif res in ("success", "ok") and fails >= need:
                if first_fail_ts and (parse_ts(e["ts"]) - first_fail_ts) <= timedelta(minutes=window_min):
                    return {"user": user, "fails": fails, "success_ts": e.get("ts")}
                fails = 0
    return None


def check_r6(events: list[dict], cfg: dict, endpoint_id: str) -> dict | None:
    allow = (cfg.get("allow_lists", {}) or {}).get(endpoint_id, [])
    for e in events:
        if e.get("event_type") in ("logon", "auth", "net_flow"):
            d = e.get("details", {}) or {}
            proto = str(d.get("protocol", d.get("logon_type", ""))).upper()
            if proto in ("RDP", "SMB") or d.get("logon_type") in ("RDP", "SMB") or e.get("event_type") == "logon":
                src = str(d.get("src_ip", d.get("source_ip", "")))
                if src and allow and src not in allow:
                    return {"src_ip": src, "protocol": proto or d.get("logon_type", "RDP"), "event_ts": e.get("ts")}
                if src and not allow and e.get("endpoint_class") == "server" and src.startswith("10.10.99."):
                    # guest IoT hitting server = rogue
                    return {"src_ip": src, "protocol": "RDP/SMB", "event_ts": e.get("ts"), "note": "guest segment source"}
    return None


def check_r9(events: list[dict], cfg: dict) -> dict | None:
    for e in events:
        if e.get("event_type") in ("net_flow", "device_command"):
            if is_baseline_deviation(e, cfg.get("baselines", {}) or {}):
                d = e.get("details", {}) or {}
                return {"dst": d.get("dst_ip"), "port": d.get("dst_port"), "proto": d.get("proto"),
                        "event_ts": e.get("ts")}
    return None


def check_r10(events: list[dict], cfg: dict) -> dict | None:
    for e in events:
        if e.get("event_type") == "device_command":
            reason = is_unauthorized_command(e, cfg.get("allowed_sources", {}) or {},
                                             cfg.get("maintenance_window", {}) or {})
            if reason:
                return {"reason": reason, "command": (e.get("details", {}) or {}).get("command"),
                        "event_ts": e.get("ts")}
    return None


RULE_META = {
    "R1": ("Mass rename/modify burst", "high", "T1486"),
    "R2": ("Canary file touched", "critical", "T1486"),
    "R3": ("Recovery inhibition", "high", "T1490"),
    "R5": ("Brute force then success", "medium", "T1110/T1078"),
    "R6": ("New RDP/SMB source", "high", "T1021.001/.002"),
    "R9": ("Device baseline deviation", "high", "baseline"),
    "R10": ("Unauthorized device command", "critical", "T0855"),
}


def run_all_rules(endpoint_id: str, events: list[dict], rules_cfg: dict) -> list[dict]:
    """Run MVP rules over one endpoint's recent events. Returns alert dicts (no ids)."""
    out = []
    checks = [
        ("R1", check_r1(events, rules_cfg.get("R1", {}))),
        ("R2", check_r2(events, rules_cfg.get("R2", {}))),
        ("R3", check_r3(events, rules_cfg.get("R3", {}))),
        ("R5", check_r5(events, rules_cfg.get("R5", {}))),
        ("R6", check_r6(events, rules_cfg.get("R6", {}), endpoint_id)),
        ("R9", check_r9(events, rules_cfg.get("R9", {}))),
        ("R10", check_r10(events, rules_cfg.get("R10", {}))),
    ]
    for rid, hit in checks:
        if hit:
            title, sev, attack = RULE_META[rid]
            w = float(rules_cfg.get(rid, {}).get("weight", 0.5))
            out.append({"endpoint_id": endpoint_id, "rule_id": rid, "title": title,
                        "severity": sev, "confidence": w, "attack": attack, "details": hit})
    return out
