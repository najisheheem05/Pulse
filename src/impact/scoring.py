"""Clinical impact scoring — rank by patient-care impact, not tech severity."""
from __future__ import annotations


def score_incident(direct_services: list[tuple[str, list[str]]],
                   lateral_services: list[str],
                   model: dict, confidence: float) -> tuple[float, list[dict]]:
    tiers = model.get("tiers", {}) or {}
    scoring = model.get("scoring", {}) or {}
    exp_dep = float(scoring.get("exposure_dependency", 0.6))
    exp_lat = float(scoring.get("exposure_lateral", 0.3))
    exp_direct = float(scoring.get("exposure_direct", 1.0))

    results: list[dict] = []
    seen: set[str] = set()
    for svc, path in direct_services:
        sdef = (model.get("services", {}) or {}).get(svc, {})
        tier = int(sdef.get("tier", 3))
        w = float((tiers.get(tier, {}) or {}).get("weight", 0.3))
        readiness = float(((sdef.get("fallback", {}) or {}).get("readiness", 0.5)))
        # direct if path len 3 (ep->app->svc), else dependency
        exposure = exp_direct if len(path) <= 3 else exp_dep
        risk = w * (1 - readiness) * exposure * confidence
        results.append({"service": svc, "tier": tier,
                        "exposure": exposure, "risk": round(risk, 3),
                        "path": path, "fallback": (sdef.get("fallback", {}) or {}).get("name", ""),
                        "max_downtime_min": sdef.get("max_downtime_min", 60),
                        "potential": False})
        seen.add(svc)
    for svc in lateral_services:
        if svc in seen:
            continue
        sdef = (model.get("services", {}) or {}).get(svc, {})
        tier = int(sdef.get("tier", 3))
        w = float((tiers.get(tier, {}) or {}).get("weight", 0.3))
        readiness = float(((sdef.get("fallback", {}) or {}).get("readiness", 0.5)))
        risk = w * (1 - readiness) * exp_lat * confidence
        results.append({"service": svc, "tier": tier,
                        "exposure": exp_lat, "risk": round(risk, 3),
                        "path": [], "fallback": (sdef.get("fallback", {}) or {}).get("name", ""),
                        "max_downtime_min": sdef.get("max_downtime_min", 60),
                        "potential": True})
    if not results:
        return 0.0, []
    results.sort(key=lambda r: r["risk"], reverse=True)
    total = results[0]["risk"] + 0.1 * sum(r["risk"] for r in results[1:])
    return round(min(100.0, total * 100), 1), results
