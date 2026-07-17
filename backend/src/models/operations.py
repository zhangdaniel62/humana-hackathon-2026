"""Validated projections used by the caller and operations interfaces."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


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

