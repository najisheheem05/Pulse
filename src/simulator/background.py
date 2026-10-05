"""Ambient hospital traffic — the 'working hospital' behind the attack demo.

Generates realistic NORMAL events (shift logons, PACS reads, device heartbeats,
backup jobs, print/camera flows). Deliberately quiet: no rule in
data/rules.yaml should fire on this traffic (see test_ambient_is_quiet).

- file ops: few per host, never renamed to .locked/.enc (R1 needs ext flips)
- logons: successes only, allow-listed or sourceless (R5 needs fails, R6 needs rogue src)
- device traffic: baseline dst/port/proto only, never device_command (R9/R10)
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


AMBIENT_HOSTS = [
    # (endpoint_id, class, source)
    ("nurse-ws-01", "workstation", "agent"),
    ("rad-ws-02", "workstation", "agent"),
    ("ehr-app-01", "server", "agent"),
    ("pacs-01", "server", "agent"),
    ("lis-01", "server", "agent"),
    ("pharm-srv-01", "server", "agent"),
    ("backup-srv-01", "server", "agent"),
    ("pump-icu-04", "device", "passive"),
    ("monitor-icu-02", "device", "passive"),
    ("vent-03", "device", "passive"),
    ("ct-01", "device", "passive"),
    ("cam-lobby-01", "iot", "passive"),
    ("printer-03", "iot", "passive"),
]

# allow-listed sources per server (mirror data/rules.yaml R6)
ALLOW_SRC = {
    "ehr-app-01": "10.10.5.10", "pacs-01": "10.10.5.20",
    "pharm-srv-01": "10.10.5.30", "lis-01": "10.10.5.31",
    "ad-01": "10.10.5.10", "filesrv-01": "10.10.5.10",
    "backup-srv-01": "10.10.5.12",
}

# baseline flows per passive device (mirror data/rules.yaml R9)
BASELINE_FLOW = {
    "pump-icu-04": ("10.10.40.4", "10.10.20.5", 8443, "tcp"),
    "monitor-icu-02": ("10.10.41.7", "10.10.20.5", 8443, "tcp"),
    "vent-03": ("10.10.40.9", "10.10.20.5", 8443, "tcp"),
    "ct-01": ("10.10.42.3", "10.10.30.8", 104, "tcp"),
    "cam-lobby-01": ("10.10.99.20", "10.10.99.2", 554, "tcp"),
    "printer-03": ("10.10.99.31", "10.10.99.3", 9100, "tcp"),
}

USERS = ["nurse_a", "nurse_b", "dr_chen", "rad_tech", "pharm_admin", "it_admin", "lab_tech"]


def _benign_file_op(rng: random.Random, ep: str) -> dict:
    kind = rng.choice(["file_modify", "file_modify", "file_modify", "file_rename"])
    if kind == "file_rename" or ep.startswith("pacs"):
        # ordinary renames WITHOUT ransomware extensions (R1 needs .locked/.enc flips)
        i = rng.randint(1, 900)
        if ep.startswith("pacs"):
            return {"event_type": "file_modify", "details": {"path": f"/pacs/studies/1.2.840.{i}.dcm", "bytes": rng.randint(200000, 4000000)}}
        return {"event_type": "file_rename",
                "details": {"old_path": f"C:/users/share/draft_{i}.tmp", "new_path": f"C:/users/share/draft_{i}.docx"}}
    i = rng.randint(1, 900)
    return {"event_type": "file_modify",
            "details": {"path": f"C:/hipaa/docs/note_{i}.txt", "bytes": rng.randint(200, 9000)}}


def generate(minutes: int = 15, seed: int = 7) -> list[dict]:
    """Normal traffic spread over the last `minutes`, ending now."""
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(minutes=minutes)
    events: list[dict] = []

    def at(frac: float) -> str:
        return _ts(start + (now - start) * frac + timedelta(seconds=rng.randint(0, 20)))

    # shift logons: successes only, allow-listed RDP or local console
    for ep in ["nurse-ws-01", "rad-ws-02", "ehr-app-01", "pacs-01", "pharm-srv-01", "lis-01"]:
        for _ in range(max(1, minutes // 5)):
            src = ALLOW_SRC.get(ep)
            details: dict = {"result": "success",
                             "logon_type": rng.choice(["RDP", "RDP", "local", "SMB"])}
            if src:
                details["src_ip"] = src
            events.append({"ts": at(rng.random()), "endpoint_id": ep,
                           "endpoint_class": "server" if "srv" in ep or "app" in ep or ep in ("pacs-01", "lis-01") else "workstation",
                           "source": "agent", "event_type": "logon",
                           "user": rng.choice(USERS), "details": details})

    # clinical file activity: sparse, benign
    for ep in ["nurse-ws-01", "rad-ws-02", "ehr-app-01", "pacs-01", "lis-01", "pharm-srv-01"]:
        for _ in range(max(1, minutes // 6)):
            op = _benign_file_op(rng, ep)
            events.append({"ts": at(rng.random()), "endpoint_id": ep,
                           "endpoint_class": "server" if ep not in ("nurse-ws-01", "rad-ws-02") else "workstation",
                           "source": "agent", "event_type": op["event_type"],
                           "user": rng.choice(USERS), "details": op["details"]})

    # device heartbeats: baseline flows only
    for ep, (src, dst, port, proto) in BASELINE_FLOW.items():
        for _ in range(max(2, minutes // 2)):
            events.append({"ts": at(rng.random()), "endpoint_id": ep,
                           "endpoint_class": "device" if not ep.startswith(("cam", "printer")) else "iot",
                           "source": "passive", "event_type": "net_flow", "user": "device",
                           "details": {"src_ip": src, "dst_ip": dst, "dst_port": port,
                                       "proto": proto, "bytes": rng.randint(300, 4000)}})

    # backup job completes normally (R3 only fires on delete/wipe/disable)
    events.append({"ts": at(0.9), "endpoint_id": "backup-srv-01", "endpoint_class": "server",
                   "source": "agent", "event_type": "backup_job", "user": "backup_svc",
                   "details": {"action": "completed", "job": "nightly_full", "gb": rng.randint(80, 160)}})
    # agent heartbeats
    for ep in ["nurse-ws-01", "ehr-app-01", "pharm-srv-01"]:
        events.append({"ts": at(rng.random()), "endpoint_id": ep,
                       "endpoint_class": "server" if ep != "nurse-ws-01" else "workstation",
                       "source": "agent", "event_type": "agent_heartbeat",
                       "user": "system", "details": {"version": "1.4.2", "status": "healthy"}})

    events.sort(key=lambda e: e["ts"])
    return events
