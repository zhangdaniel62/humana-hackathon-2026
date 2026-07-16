"""Pydantic v2 data models shared across agents.

Only the models the ROI Gatekeeper needs live here for now; the other agents
(Claim Story, Benefits Q&A, Sentinel) will add theirs to this module.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ROIStatus(str, Enum):
    """Outcome of the Release-of-Information authorization check."""

    VERIFIED = "verified"          # caller is authorized for this member
    MISSING = "missing"            # no valid authorization on file
    NOT_REQUIRED = "not_required"  # caller is the member themselves


class ROICheckResult(BaseModel):
    """Structured, deterministic result of an ROI check. The LLM narrates this;
    it never produces the `status` itself (plan §8 guardrail)."""

    status: ROIStatus
    subject_member_id: str
    caller_name: str
    # Populated only when a matching authorization row was found:
    matched_auth_id: str | None = None
    relationship: str | None = None
    expiration_date: str | None = None
    # Machine-readable reason, useful for the dashboard / debugging:
    #   self | authorized | no_authorization | not_on_file | expired | unknown_member
    reason: str
    # Human-facing text the agent can read out. For `missing` this is the
    # self-service ROI-submission path.
    message: str


class AgentEvent(BaseModel):
    """Fire-and-forget event appended to the EventLog and consumed by Sentinel."""

    timestamp: datetime
    session_id: str
    agent: str
    event_type: str  # e.g. roi_gap_detected, roi_verified
    payload: dict = Field(default_factory=dict)
