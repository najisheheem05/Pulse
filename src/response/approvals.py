"""Approval queue (single analyst approve for hackathon)."""
from __future__ import annotations
import sqlite3
from ..core import store as S


def request_action(db: str, incident_id: str, action: str, risk_tier: str, reason: str = "") -> dict:
    aid = S.new_id("act")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO actions(id,incident_id,action,risk_tier,status,requested_at,decided_at,approver,reason)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (aid, incident_id, action, risk_tier, "pending", S.now_iso(), "", "", reason))
    conn.commit()
    conn.close()
    return {"id": aid, "incident_id": incident_id, "action": action, "status": "pending"}


def decide(db: str, action_id: str, approve: bool, approver: str = "analyst") -> dict | None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
    if not r:
        conn.close()
        return None
    status = "approved" if approve else "denied"
    conn.execute("UPDATE actions SET status=?, decided_at=?, approver=? WHERE id=?",
                 (status, S.now_iso(), approver, action_id))
    conn.commit()
    conn.close()
    d = dict(r)
    d["status"] = status
    return d


def list_actions(db: str, incident_id: str | None = None) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    if incident_id:
        rows = conn.execute("SELECT * FROM actions WHERE incident_id=? ORDER BY requested_at DESC",
                            (incident_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM actions ORDER BY requested_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]
