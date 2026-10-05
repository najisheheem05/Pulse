"""Plain-English explanations for the panel + fallback guidance."""
from __future__ import annotations


def explain_incident(endpoint_id: str, rule_ids: list[str], confidence: float,
                     services: list[dict], endpoint_class: str = "") -> str:
    if not services:
        return (f"No patient-care service maps to {endpoint_id}. "
                f"Rules {','.join(rule_ids)} fired with confidence {confidence}; "
                "treat as IT-only, monitor and review.")
    top = services[0]
    others = ", ".join(f"{s['service']} (T{s['tier']})" for s in services[1:3])
    path = " → ".join(top.get("path", [])) if top.get("path") else "via network reachability (potential lateral)"
    base = (f"{endpoint_id} shows {' + '.join(rule_ids)} "
            f"(confidence {confidence:.2f}). It supports {top['service']} "
            f"(Tier {top['tier']}, fallback: {top['fallback']}, "
            f"max downtime {top['max_downtime_min']} min) via {path}.")
    if top.get("potential"):
        base += " Exposure is POTENTIAL (lateral reach), not confirmed."
    if others:
        base += f" Also at risk: {others}."
    if endpoint_class in ("device", "iot"):
        base += " Medical/IoT device: passive monitoring + approved segmentation change only — never auto-isolate."
    elif top["tier"] == 1:
        base += " Tier-1: activate fallback early and require analyst approval before any isolation."
    return base
