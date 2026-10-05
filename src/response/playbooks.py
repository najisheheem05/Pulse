"""Response playbooks: recommend action by risk tier. Devices never auto-contained."""
from __future__ import annotations


def recommend(top_tier: int | None, endpoint_class: str, risk_score: float) -> dict:
    is_device = endpoint_class in ("device", "iot")
    if is_device:
        return {"action": "passive_monitoring_and_segment_review",
                "approval": "required", "auto": False,
                "text": "Passive monitoring plus a segmentation/ACL change that needs analyst approval. "
                        "Never auto-isolate a medical device."}
    if top_tier == 1 or risk_score >= 40:
        return {"action": "isolate_host_pending_approval", "approval": "required",
                "auto": False, "needs_clinical": True,
                "text": "Recommend isolation / block outbound + disable user. Requires analyst approval "
                        "(clinical notified for Tier-1)."}
    if (top_tier == 2) or (15 <= risk_score < 40):
        return {"action": "disable_user_block_outbound", "approval": "required",
                "auto": False,
                "text": "Recommend disable user + block outbound. Requires analyst approval."}
    return {"action": "raise_alert_snapshot_logs", "approval": "auto",
            "auto": True, "text": "Low risk: raise alert, snapshot logs, increase logging. Automatic."}
