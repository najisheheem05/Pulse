"""Hash-chained audit log (~30 lines core). Tamper-evident."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from ..core import store as S


def _hash(prev: str, ts: str, actor: str, action: str, incident_id: str, payload: str) -> str:
    h = hashlib.sha256()
    h.update(f"{prev}|{ts}|{actor}|{action}|{incident_id}|{payload}".encode())
    return h.hexdigest()


def append(db: str, actor: str, action: str, incident_id: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    pstr = json.dumps(payload, sort_keys=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    last = conn.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev = last["hash"] if last else "GENESIS"
    ts = S.now_iso()
    digest = _hash(prev, ts, actor, action, incident_id, pstr)
    conn.execute(
        "INSERT INTO audit(ts,actor,action,incident_id,payload,prev_hash,hash) VALUES(?,?,?,?,?,?,?)",
        (ts, actor, action, incident_id, pstr, prev, digest))
    conn.commit()
    conn.close()
    return {"ts": ts, "prev_hash": prev, "hash": digest}


def fetch(db: str, limit: int = 200) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def verify(db: str) -> dict:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM audit ORDER BY seq ASC").fetchall()
    conn.close()
    prev = "GENESIS"
    for r in rows:
        expect = _hash(prev, r["ts"], r["actor"], r["action"], r["incident_id"], r["payload"])
        if expect != r["hash"] or r["prev_hash"] != prev:
            return {"ok": False, "tampered_seq": r["seq"], "checked": len(rows)}
        prev = r["hash"]
    return {"ok": True, "checked": len(rows)}
