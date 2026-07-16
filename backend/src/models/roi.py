"""Release-of-Information contracts shared by the ROI gate and orchestrator."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ROIStatus(StrEnum):
    """Deterministic disclosure outcomes for a caller/member pairing."""

    VERIFIED = "verified"
    MISSING = "missing"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class ROICheckResult(BaseModel):
    """Structured result narrated by agents but decided by deterministic code."""

    model_config = ConfigDict(extra="forbid")

    status: ROIStatus
    subject_member_id: str
    caller_name: str
    matched_auth_id: str | None = None
    relationship: str | None = None
    expiration_date: str | None = None
    reason: str
    message: str
