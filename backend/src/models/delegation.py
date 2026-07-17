"""Metadata-only specialist handoff trace contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DelegationTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    session_id: str
    work_item_id: str | None = None
    specialist: str
    started_at: datetime
    completed_at: datetime
    latency_ms: float = Field(ge=0)
    outcome: Literal["success", "fallback", "blocked"]
    error_code: str | None = None
