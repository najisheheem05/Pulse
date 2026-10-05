"""Unified event schema — one format for agent + passive telemetry."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


EndpointClass = Literal["workstation", "server", "device", "iot", "network"]
Source = Literal["agent", "passive"]
EventType = Literal[
    "file_rename", "file_modify", "process_start",
    "logon", "net_flow", "device_command",
    "auth", "backup_job", "agent_heartbeat",
]


class Event(BaseModel):
    ts: str = Field(description="ISO8601 UTC, e.g. 2026-10-10T10:41:07Z")
    endpoint_id: str
    endpoint_class: EndpointClass = "workstation"
    source: Source = "agent"
    event_type: EventType
    user: str = "unknown"
    details: dict[str, Any] = Field(default_factory=dict)

    def ts_dt(self) -> datetime:
        s = self.ts.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class Alert(BaseModel):
    id: str = ""
    ts: str = ""
    endpoint_id: str = ""
    rule_id: str = ""
    title: str = ""
    severity: str = "medium"  # low|medium|high|critical
    confidence: float = 0.5
    attack: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str = ""
    endpoint_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    rule_ids: list[str] = Field(default_factory=list)
    alert_count: int = 0
    confidence: float = 0.0
    risk_score: float = 0.0
    services_at_risk: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[list[str]] = Field(default_factory=list)
    explanation: str = ""
    status: str = "open"  # open|contained|closed
