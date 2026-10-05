"""Build data/scenarios/e_hospital_campaign.json — a connected, plausible hospital kill chain.

'After-hours affiliate' (02:10–02:58, compressed night shift):
  P0 ambient night-shift traffic (quiet)
  P1 initial access: vendor VPN brute-force -> success (R5)            T1110/T1078
  P2 foothold+execution: nurse workstation ransomware (R1+R2+R3)       T1486/T1490
  P3 lateral: jump -> file server + AD + pharmacy server (R6 x3)       T1021
  P4 crown jewels: pharmacy server ransomware (R1+R2+R3) -> T1 incident
  P5 IoMT pivot: lobby camera -> infusion pump rogue commands (R9+R10) T0855
  P6 recovery kill: backup catalog wipe (R3)                           T1490

Run: python3 scripts/make_campaign.py  (rewrites the JSON)
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone

BASE = datetime(2026, 10, 10, 2, 10, 0, tzinfo=timezone.utc)


def ts(sec: int) -> str:
    return (BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(sec: int, endpoint_id: str, eclass: str, source: str, etype: str,
       user: str, note: str = "", **details) -> dict:
    if note:
        details = {**details, "note": note}
    return {"ts": ts(sec), "endpoint_id": endpoint_id, "endpoint_class": eclass,
            "source": source, "event_type": etype, "user": user, "details": details}


def build() -> list[dict]:
    evs: list[dict] = []

    # ---- P0 ambient (02:10-02:13) ----
    evs += [
        ev(0, "nurse-ws-01", "workstation", "agent", "logon", "nurse_a",
           result="success", logon_type="local"),
        ev(40, "pump-icu-04", "device", "passive", "net_flow", "device",
           src_ip="10.10.40.4", dst_ip="10.10.20.5", dst_port=8443, proto="tcp", bytes=640),
        ev(90, "pacs-01", "server", "agent", "file_modify", "rad_tech",
           path="/pacs/studies/1.2.840.113619.dcm", bytes=2100000),
        ev(150, "monitor-icu-02", "device", "passive", "net_flow", "device",
           src_ip="10.10.41.7", dst_ip="10.10.20.5", dst_port=8443, proto="tcp", bytes=900),
    ]

    # ---- P1 initial access (02:14-02:17): vendor VPN brute force ----
    for i in range(6):
        evs.append(ev(240 + i * 30, "vpn-jump-01", "server", "agent", "logon", "vendor",
                       "P1: password spraying the vendor VPN account",
                       result="fail", logon_type="RDP", src_ip="203.0.113.9"))
    evs.append(ev(430, "vpn-jump-01", "server", "agent", "logon", "vendor",
                   "P1: success — attacker holds a valid vendor session",
                   result="success", logon_type="RDP", src_ip="203.0.113.9"))

    # ---- P2 foothold + execution (02:21-02:26): nurse workstation ----
    for i in range(18):
        evs.append(ev(660 + i * 8, "nurse-ws-01", "workstation", "agent", "file_rename", "nurse_a",
                       "P2: affiliate payload encrypting the nursing share",
                       old_path=f"C:/hipaa/docs/chart_{i:03d}.pdf",
                       new_path=f"C:/hipaa/docs/chart_{i:03d}.pdf.locked"))
    evs.append(ev(820, "nurse-ws-01", "workstation", "agent", "file_modify", "nurse_a",
                   "P2: canary tripped mid-encryption",
                   path="/shares/finance/__canary_do_not_touch.txt", bytes=12))
    evs.append(ev(850, "nurse-ws-01", "workstation", "agent", "process_start", "nurse_a",
                   "P2: killing recovery before moving on",
                   process="powershell.exe", parent="winword.exe",
                   commandline="powershell -enc aQBmACgAdgBzAHMAYQBkAG0AaQBuACAAZABlAGwAZQB0AGUAIABzAGgAYQBkAG8AdwBzACAALwBhAGwAbAAgAC8AcQB1AGkAZQB0ACkA"))

    # vssadmin in clear as well so R3 fires on the literal pattern too
    evs.append(ev(860, "nurse-ws-01", "workstation", "agent", "process_start", "nurse_a",
                   process="cmd.exe", parent="powershell.exe",
                   commandline="vssadmin delete shadows /all /quiet"))

    # ---- P3 lateral (02:33-02:35): jump box -> core ----
    evs.append(ev(1380, "filesrv-01", "server", "agent", "logon", "vendor",
                   "P3: first hop — file server from an unknown internal host",
                   result="success", logon_type="RDP", src_ip="10.10.6.12"))
    evs.append(ev(1440, "ad-01", "server", "agent", "logon", "vendor",
                   "P3: touching domain services (privilege escalation staging)",
                   result="success", logon_type="SMB", src_ip="10.10.6.12"))
    evs.append(ev(1500, "pharm-srv-01", "server", "agent", "logon", "vendor",
                   "P3: crown jewels — pharmacy server over SMB, unknown source",
                   result="success", logon_type="SMB", src_ip="10.10.6.99"))

    # ---- P4 crown jewels (02:36-02:41): pharmacy ransomware ----
    for i in range(20):
        evs.append(ev(1560 + i * 7, "pharm-srv-01", "server", "agent", "file_rename", "pharm_admin",
                       "P4: same affiliate playbook, Tier-1 target",
                       old_path=f"D:/pharma/dispense_{i:03d}.db",
                       new_path=f"D:/pharma/dispense_{i:03d}.db.locked"))
    evs.append(ev(1720, "pharm-srv-01", "server", "agent", "file_modify", "pharm_admin",
                   path="C:\\canary\\patient_list_decoy.xlsx", bytes=8))
    evs.append(ev(1750, "pharm-srv-01", "server", "agent", "process_start", "pharm_admin",
                   process="powershell.exe", parent="services.exe",
                   commandline="wbadmin delete catalog -quiet"))

    # ---- P5 IoMT pivot (02:47-02:50): lobby camera -> infusion pump ----
    evs.append(ev(2220, "cam-lobby-01", "iot", "passive", "net_flow", "device",
                   "P5: camera starts scanning the clinical VLAN (pivot beachhead)",
                   src_ip="10.10.99.20", dst_ip="10.10.40.4", dst_port=445, proto="tcp", bytes=2100))
    evs.append(ev(2260, "pump-icu-04", "device", "passive", "net_flow", "unknown",
                   "P5: pump talking to something that is not its server",
                   src_ip="10.10.40.4", dst_ip="10.10.99.20", dst_port=23, proto="tcp", bytes=1400))
    evs.append(ev(2300, "pump-icu-04", "device", "passive", "device_command", "unknown",
                   "P5: rogue dose-rate command from the camera's subnet",
                   command="dose_rate", param="12.5ml/h", src_ip="10.10.99.20", **{"from": "10.10.99.20"}))
    evs.append(ev(2340, "pump-icu-04", "device", "passive", "device_command", "unknown",
                   "P5: safety limits disabled — worst case for the panel",
                   command="set_config", param="rate_limit=off", src_ip="10.10.99.20", **{"from": "10.10.99.20"}))

    # ---- P6 recovery kill (02:55): backup catalog wipe ----
    evs.append(ev(2700, "backup-srv-01", "server", "agent", "backup_job", "backup_svc",
                   "P6: affiliate burns the recovery path last",
                   action="delete_catalog", job="nightly_full", gb=0))

    # ---- tail: hospital keeps breathing ----
    evs += [
        ev(2820, "vent-03", "device", "passive", "net_flow", "device",
           src_ip="10.10.40.9", dst_ip="10.10.20.5", dst_port=8443, proto="tcp", bytes=700),
        ev(2880, "ehr-app-01", "server", "agent", "logon", "dr_chen",
           result="success", logon_type="RDP", src_ip="10.10.5.10"),
    ]

    evs.sort(key=lambda e: e["ts"])
    return evs


if __name__ == "__main__":
    events = build()
    with open("data/scenarios/e_hospital_campaign.json", "w") as f:
        json.dump(events, f, indent=1)
    from collections import Counter
    print(f"wrote {len(events)} events -> data/scenarios/e_hospital_campaign.json")
    print(Counter(e["endpoint_id"] for e in events))
