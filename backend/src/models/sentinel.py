from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(StrEnum):
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"
    DENIAL_EXPLAINED = "denial_explained"
    ROI_GAP_DETECTED = "roi_gap_detected"
    COVERAGE_QUESTION_ANSWERED = "coverage_question_answered"
    ESCALATION_TRIGGERED = "escalation_triggered"
    COMPLIANCE_FLAG_DETECTED = "compliance_flag_detected"


class AlertType(StrEnum):
    DENIAL_SPIKE = "denial_spike"
    ROI_GAP_FREQUENCY = "roi_gap_frequency"
    REPEAT_CONTACT = "repeat_contact"
    ESCALATION = "escalation"
    COMPLIANCE_RISK = "compliance_risk"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utc_now)
    session_id: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    event_type: EventType
    member_id: str | None = None
    claim_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SentinelAlert(StrictModel):
    alert_id: UUID = Field(default_factory=uuid4)
    dedup_key: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    recommended_action: str
    first_seen: datetime
    last_seen: datetime
    occurrences: int = Field(default=1, ge=1)
    evidence_event_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class MetricsBaseline(StrictModel):
    """Explicit, user-supplied demo assumptions; never inferred from quality data."""

    aht_minutes: float | None = Field(default=None, ge=0)
    fcr_rate: float | None = Field(default=None, ge=0, le=1)
    repeat_contact_rate: float | None = Field(default=None, ge=0, le=1)
    source_note: str = "No baseline assumptions supplied"


class MetricsSnapshot(StrictModel):
    completed_sessions: int = 0
    average_handle_time_minutes: float | None = None
    first_contact_resolution_rate: float | None = None
    repeat_contact_rate: float | None = None
    escalation_rate: float | None = None
    preventable_denials_caught: int = 0
    baseline: MetricsBaseline = Field(default_factory=MetricsBaseline)
    aht_change_rate: float | None = None
    fcr_change_rate: float | None = None
    repeat_contact_change_rate: float | None = None


class SentinelSnapshot(StrictModel):
    generated_at: datetime = Field(default_factory=utc_now)
    processed_event_count: int
    dropped_event_count: int
    active_alert_count: int
    alerts: list[SentinelAlert]
    metrics: MetricsSnapshot
