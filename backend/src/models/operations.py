"""Validated projections used by the caller and operations interfaces."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .sentinel import MetricsBaseline


class NotificationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: UUID = Field(default_factory=uuid4)
    claim_id: str
    member_id: str
    audience: Literal["member_and_provider"] = "member_and_provider"
    channel: Literal["portal_message"] = "portal_message"
    status: Literal["preview"] = "preview"
    delivery_status: Literal["not_sent"] = "not_sent"
    subject: str
    message: str
    evidence: list[dict[str, Any]]
    recommended_actions: list[str]
    grounding: dict[str, Any]
    data_label: Literal["synthetic_demo_data"] = "synthetic_demo_data"


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: Literal["ready", "incomplete"]
    caller_name: str | None = None
    subject_member_id: str | None = None
    language: str | None = None
    roi: dict[str, Any] | None = None
    claim: dict[str, Any] | None = None
    benefits: dict[str, Any] | None = None
    readiness: dict[str, Any] | None = None
    notification_preview: NotificationPreview | None = None
    intent_history: list[str] = Field(default_factory=list)
    missing_findings: list[str] = Field(default_factory=list)


class OperationsDashboardMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_label: Literal["synthetic_demo"] = "synthetic_demo"
    start: date
    end: date
    bucket: Literal["week", "month"]
    repeat_window_days: Literal[7] = 7
    observation_cutoff: datetime | None = None


class OperationsMetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_sessions: int = Field(ge=0)
    average_handle_time_minutes: float | None = None
    mature_initial_contacts: int = Field(ge=0)
    first_contact_resolution_rate: float | None = None
    repeat_contact_rate: float | None = None
    automated_calls: int = Field(ge=0)
    manual_review_calls: int = Field(ge=0)


class OperationsTrendPoint(OperationsMetricSummary):
    period_start: date


class InterventionFunnel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identified_claims: int = Field(ge=0)
    recommended_claims: int = Field(ge=0)
    recorded_claims: int = Field(ge=0)
    recorded_coverage_rate: float | None = None


class RepWorkload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    manual_review_calls: int = Field(ge=0)


class OperationsDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: OperationsDashboardMetadata
    baseline: MetricsBaseline
    summary: OperationsMetricSummary
    trend: list[OperationsTrendPoint]
    interventions: InterventionFunnel
    manual_by_rep: list[RepWorkload]
