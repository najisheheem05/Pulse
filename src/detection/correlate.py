"""Correlator: alerts on same endpoint within window -> one incident. Noisy-OR confidence."""
from __future__ import annotations
import math
from datetime import datetime, timezone


def noisy_or(weights: list[float]) -> float:
    p = 1.0
    for w in weights:
        p *= (1.0 - max(0.0, min(0.99, float(w))))
    return round(1.0 - p, 3)


def correlate(endpoint_id: str, alerts: list[dict], rules_cfg: dict) -> dict:
    rule_ids = sorted({a["rule_id"] for a in alerts})
    weights = [float(rules_cfg.get(r, {}).get("weight", a.get("confidence", 0.5)))
               for r in rule_ids for a in alerts if a["rule_id"] == r][:len(rule_ids)]
    # simpler: one weight per rule
    weights = [float(rules_cfg.get(r, {}).get("weight", 0.5)) for r in rule_ids]
    conf = noisy_or(weights) if weights else 0.0
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"endpoint_id": endpoint_id, "rule_ids": rule_ids,
            "alert_count": len(alerts), "confidence": conf,
            "created_at": now, "updated_at": now}
