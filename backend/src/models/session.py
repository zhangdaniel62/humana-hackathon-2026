"""Shared member-session contracts used by the root orchestrator."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .roi import ROICheckResult


class MemberSessionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    caller_name: str
    subject_member_id: str
    language: str
    roi: ROICheckResult
