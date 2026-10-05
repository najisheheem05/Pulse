"""SQLite store (stdlib sqlite3). Zero-setup, one file."""
from __future__ import annotations
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.environ.get("DATABASE_PATH", "hospital.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, endpoint_id TEXT, endpoint_class TEXT,
  source TEXT, event_type TEXT, user TEXT, details TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY, ts TEXT, endpoint_id TEXT, rule_id TEXT,
  title TEXT, severity TEXT, confidence REAL, attack TEXT, details TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, endpoint_id TEXT, created_at TEXT, updated_at TEXT,
  rule_ids TEXT, alert_count INTEGER, confidence REAL, risk_score REAL,
  services TEXT, paths TEXT, explanation TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY, incident_id TEXT, action TEXT, risk_tier TEXT,
  status TEXT, requested_at TEXT, decided_at TEXT, approver TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, actor TEXT, action TEXT, incident_id TEXT,
  payload TEXT, prev_hash TEXT, hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ep_ts ON events(endpoint_id, ts);
CREATE INDEX IF NOT EXISTS idx_alerts_ep ON alerts(endpoint_id);
"""


def init_db(path: str = DB_PATH) -> None:
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def reset_db(path: str = DB_PATH) -> None:
    conn = connect(path)
    for t in ("events", "alerts", "incidents", "actions", "audit"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()


def insert_event(path: str, ev: dict) -> None:
    conn = connect(path)
    conn.execute(
        "INSERT INTO events(ts,endpoint_id,endpoint_class,source,event_type,user,details)"
        " VALUES(?,?,?,?,?,?,?)",
        (ev.get("ts"), ev.get("endpoint_id"), ev.get("endpoint_class"),
         ev.get("source"), ev.get("event_type"), ev.get("user"),
         json.dumps(ev.get("details", {}))),
    )
    conn.commit()
    conn.close()


def fetch_events(path: str, endpoint_id: str | None = None, limit: int = 5000) -> list[dict]:
    conn = connect(path)
    if endpoint_id:
        rows = conn.execute(
            "SELECT * FROM events WHERE endpoint_id=? ORDER BY ts DESC LIMIT ?",
            (endpoint_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d["details"] or "{}")
        except Exception:
            d["details"] = {}
        out.append(d)
    return out


def insert_alert(path: str, a: dict) -> None:
    conn = connect(path)
    conn.execute(
        "INSERT OR REPLACE INTO alerts(id,ts,endpoint_id,rule_id,title,severity,confidence,attack,details)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (a["id"], a["ts"], a["endpoint_id"], a["rule_id"], a["title"],
         a["severity"], a["confidence"], a.get("attack", ""),
         json.dumps(a.get("details", {}))),
    )
    conn.commit()
    conn.close()


def fetch_alerts(path: str, endpoint_id: str | None = None) -> list[dict]:
    conn = connect(path)
    if endpoint_id:
        rows = conn.execute("SELECT * FROM alerts WHERE endpoint_id=? ORDER BY ts", (endpoint_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM alerts ORDER BY ts").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d["details"] or "{}")
        except Exception:
            d["details"] = {}
        out.append(d)
    return out


def upsert_incident(path: str, inc: dict) -> None:
    conn = connect(path)
    conn.execute(
        "INSERT OR REPLACE INTO incidents(id,endpoint_id,created_at,updated_at,rule_ids,alert_count,"
        "confidence,risk_score,services,paths,explanation,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (inc["id"], inc["endpoint_id"], inc["created_at"], inc["updated_at"],
         json.dumps(inc.get("rule_ids", [])), inc.get("alert_count", 0),
         inc.get("confidence", 0.0), inc.get("risk_score", 0.0),
         json.dumps(inc.get("services_at_risk", [])), json.dumps(inc.get("paths", [])),
         inc.get("explanation", ""), inc.get("status", "open")),
    )
    conn.commit()
    conn.close()


def fetch_incidents(path: str) -> list[dict]:
    conn = connect(path)
    rows = conn.execute("SELECT * FROM incidents ORDER BY risk_score DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("rule_ids", "services", "paths"):
            try:
                d[k] = json.loads(d[k] or ("[]" if k != "services" else "[]"))
            except Exception:
                d[k] = []
        # normalize key name
        d["services_at_risk"] = d.pop("services")
        out.append(d)
    return out


def count_events(path: str, since: str | None = None) -> int:
    conn = connect(path)
    if since:
        n = conn.execute("SELECT COUNT(*) c FROM events WHERE ts >= ?", (since,)).fetchone()["c"]
    else:
        n = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
    conn.close()
    return int(n)


def max_event_ts(path: str) -> str | None:
    conn = connect(path)
    r = conn.execute("SELECT MAX(ts) m FROM events").fetchone()
    conn.close()
    return r["m"] if r else None


def count_alerts(path: str) -> int:
    conn = connect(path)
    n = conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]
    conn.close()
    return int(n)


def recent_alert_ts(path: str, limit: int = 300) -> list[str]:
    conn = connect(path)
    rows = conn.execute("SELECT ts FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [r["ts"] for r in rows]


def fetch_incident(path: str, inc_id: str) -> dict | None:
    conn = connect(path)
    r = conn.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    for k in ("rule_ids", "services", "paths"):
        try:
            d[k] = json.loads(d[k] or "[]")
        except Exception:
            d[k] = []
    d["services_at_risk"] = d.pop("services")
    return d


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
