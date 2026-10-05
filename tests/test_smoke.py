"""Smoke tests: rules, impact, audit — run with pytest -q."""
import pytest
from src.core import store as S
from src.detection import engine as DE, correlate as CO
from src.detection.baseline import is_baseline_deviation, is_unauthorized_command
from src.impact import graph as IG, scoring as IS, explain as IE
from src.response import playbooks as RP, audit as AU
from yaml import safe_load


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    S.init_db(str(db))
    yield str(db)


def test_rules_r1_mass_rename(fresh_db):
    events = []
    base = "2026-10-10T10:40:00Z"
    for i in range(20):
        events.append({"ts": base, "endpoint_id": "ws-1", "endpoint_class": "workstation",
                       "source": "agent", "event_type": "file_rename", "user": "u",
                       "details": {"old_path": f"C:/a/{i}.txt", "new_path": f"C:/a/{i}.locked"}})
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("ws-1", events, rcfg)
    r1 = [a for a in alerts if a["rule_id"] == "R1"]
    assert r1, "R1 should fire on 20 renames with extension flip"


def test_rules_r2_canary(fresh_db):
    events = [{"ts": "2026-10-10T10:40:00Z", "endpoint_id": "ws-1", "endpoint_class": "workstation",
               "source": "agent", "event_type": "file_modify", "user": "u",
               "details": {"path": "/shares/finance/__canary_do_not_touch.txt"}}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("ws-1", events, rcfg)
    assert any(a["rule_id"] == "R2" for a in alerts)


def test_rules_r3_recovery(fresh_db):
    events = [{"ts": "2026-10-10T10:40:00Z", "endpoint_id": "srv-1", "endpoint_class": "server",
               "source": "agent", "event_type": "process_start", "user": "u",
               "details": {"commandline": "vssadmin delete shadows /all /quiet"}}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("srv-1", events, rcfg)
    assert any(a["rule_id"] == "R3" for a in alerts)


def test_rules_r5_bruteforce(fresh_db):
    events = []
    base = "2026-10-10T10:40:00Z"
    for i in range(6):
        events.append({"ts": base, "endpoint_id": "ws-1", "endpoint_class": "workstation",
                       "source": "agent", "event_type": "logon", "user": "u",
                       "details": {"result": "fail", "logon_type": "RDP", "src_ip": "10.10.99.50"}})
    events.append({"ts": base, "endpoint_id": "ws-1", "endpoint_class": "workstation",
                   "source": "agent", "event_type": "logon", "user": "u",
                   "details": {"result": "success", "logon_type": "RDP", "src_ip": "10.10.99.50"}})
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("ws-1", events, rcfg)
    assert any(a["rule_id"] == "R5" for a in alerts)


def test_rules_r6_new_rdp(fresh_db):
    events = [{"ts": "2026-10-10T10:40:00Z", "endpoint_id": "ehr-app-01", "endpoint_class": "server",
               "source": "agent", "event_type": "logon", "user": "u",
               "details": {"result": "success", "logon_type": "RDP", "src_ip": "10.10.99.99"}}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("ehr-app-01", events, rcfg)
    assert any(a["rule_id"] == "R6" for a in alerts)


def test_rules_r9_baseline(fresh_db):
    events = [{"ts": "2026-10-10T10:40:00Z", "endpoint_id": "pump-icu-04", "endpoint_class": "device",
               "source": "passive", "event_type": "net_flow", "user": "device",
               "details": {"src_ip": "10.10.40.4", "dst_ip": "10.10.99.99", "dst_port": 23, "proto": "tcp"}}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("pump-icu-04", events, rcfg)
    assert any(a["rule_id"] == "R9" for a in alerts)


def test_rules_r10_unauth_cmd(fresh_db):
    events = [{"ts": "2026-10-10T10:40:00Z", "endpoint_id": "pump-icu-04", "endpoint_class": "device",
               "source": "passive", "event_type": "device_command", "user": "unknown",
               "details": {"command": "dose_rate", "param": "12.5ml/h", "src_ip": "10.10.99.99"}}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("pump-icu-04", events, rcfg)
    assert any(a["rule_id"] == "R10" for a in alerts)


def test_correlate_noisy_or(fresh_db):
    alerts = [{"rule_id": "R1", "confidence": 0.6}, {"rule_id": "R2", "confidence": 0.8}, {"rule_id": "R3", "confidence": 0.7}]
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    corr = CO.correlate("ws-1", alerts, rcfg)
    # noisy-OR: 1 - (1-0.6)*(1-0.8)*(1-0.7) = 1 - 0.4*0.2*0.3 = 1 - 0.024 = 0.976
    assert corr["confidence"] > 0.95


def test_impact_scoring(fresh_db):
    # mock direct path: ws -> app -> svc (tier 1)
    direct = [("medication_administration", ["ws-1", "ehr_client", "ehr", "medication_administration"])]
    lateral = ["imaging_reads"]
    model = IG.load_model()
    risk, svcs = IS.score_incident(direct, lateral, model, 0.9)
    assert risk > 20  # tier 1, high confidence -> ~36
    assert svcs[0]["service"] == "medication_administration"
    assert svcs[0]["tier"] == 1
    assert svcs[0]["exposure"] in (1.0, 0.6)  # direct if path len<=3 else dependency
    # lateral should be potential
    lat = [s for s in svcs if s.get("potential")]
    assert lat and lat[0]["service"] == "imaging_reads"
    assert lat[0]["exposure"] == 0.3


def test_explain_contains_keywords(fresh_db):
    model = IG.load_model()
    direct = [("medication_administration", ["ws-1", "ehr_client", "ehr", "medication_administration"])]
    lateral = []
    risk, svcs = IS.score_incident(direct, lateral, model, 0.9)
    exp = IE.explain_incident("ws-1", ["R1", "R3"], 0.9, svcs, "workstation")
    assert "medication_administration" in exp
    assert "Tier 1" in exp
    assert "Paper MAR" in exp or "fallback" in exp.lower()


def test_playbook_device_never_auto(fresh_db):
    rec = RP.recommend(1, "device", 80)
    assert rec["auto"] is False
    assert "never auto-isolate" in rec["text"].lower()


def test_audit_chain(fresh_db):
    AU.append(fresh_db, "analyst", "test", "inc-1", {"foo": "bar"})
    AU.append(fresh_db, "analyst", "test2", "inc-1", {"foo": "baz"})
    v = AU.verify(fresh_db)
    assert v["ok"] is True
    # tamper
    import sqlite3
    conn = sqlite3.connect(fresh_db)
    conn.execute("UPDATE audit SET payload='tampered' WHERE seq=1")
    conn.commit()
    conn.close()
    v2 = AU.verify(fresh_db)
    assert v2["ok"] is False


# run the sim scenarios end-to-end via API (requires running server)
def test_scenario_a_radiology(fresh_db):
    import json
    with open("data/scenarios/a_radiology.json") as f:
        events = json.load(f)
    for ev in events:
        S.insert_event(fresh_db, ev)
    with open("data/rules.yaml") as f:
        rcfg = safe_load(f)["rules"]
    alerts = DE.run_all_rules("rad-ws-02", events, rcfg)
    # should have R1, R2, R3, R5, R6
    rule_ids = {a["rule_id"] for a in alerts}
    assert "R1" in rule_ids and "R2" in rule_ids and "R3" in rule_ids