"""Device baselines for agentless endpoints (IoMT/IoT)."""
from __future__ import annotations


def _norm_proto(p) -> str:
    return str(p or "tcp").lower()


def is_baseline_deviation(event: dict, baselines: dict) -> bool:
    """True if dst/port/proto outside learned baseline for this endpoint."""
    ep = event.get("endpoint_id", "")
    allowed = baselines.get(ep)
    if not allowed:
        return False  # unknown device -> don't fire R9, R10 handles it
    d = event.get("details", {}) or {}
    dst = str(d.get("dst_ip", d.get("dst", "")))
    port = int(d.get("dst_port", d.get("port", 0)) or 0)
    proto = _norm_proto(d.get("proto", d.get("protocol", "tcp")))
    for a in allowed:
        if (str(a.get("dst")) == dst and int(a.get("port")) == port
                and _norm_proto(a.get("proto")) == proto):
            return False
    return True


def is_unauthorized_command(event: dict, allowed_sources: dict, window: dict) -> str | None:
    """Return reason string if device_command is unauthorized, else None."""
    ep = event.get("endpoint_id", "")
    d = event.get("details", {}) or {}
    src = str(d.get("src_ip", d.get("source_ip", d.get("from", ""))))
    allowed = allowed_sources.get(ep, [])
    if allowed and src and src not in allowed:
        return f"source {src} not in allow-list {allowed}"
    if allowed and not src:
        return "missing source for device command"
    # maintenance window check (informational — still flag outside window)
    try:
        from datetime import datetime
        ts = event.get("ts", "")
        hhmm = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
        start, end = window.get("start", "02:00"), window.get("end", "04:00")
        if allowed and src in allowed and not (start <= hhmm <= end):
            # allow-listed but outside window -> still note, only flag if config change
            if str(d.get("command", "")).lower() in ("set_config", "firmware_update", "dose_rate", "reboot"):
                return f"config command outside maintenance window {start}-{end} (ts {hhmm})"
    except Exception:
        pass
    return None
