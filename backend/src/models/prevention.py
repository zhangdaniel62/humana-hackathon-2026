"""Typed contracts for proactive scanning and the representative queue."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkItemStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=500, ge=1, le=5_000)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key must not be blank")
        return normalized


class GoldenPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(
        default="golden-path-v2", min_length=1, max_length=128
    )

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key must not be blank")
        return normalized


class ScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    idempotency_key: str
    source: Literal["startup", "manager", "golden_path"]
    completed_at: datetime
    claims_scanned: int = Field(ge=0)
    items_created: int = Field(ge=0)
    items_existing: int = Field(ge=0)
    replayed: bool = False


class WorkItemCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    rule_id: str
    title: str
    recommended_action: str
    risk_band: Literal["high", "warning"]
    priority_score: int = Field(ge=0)


class RepWorkItem(BaseModel):
    """Narrow queue projection; intentionally excludes member/session facts."""

    model_config = ConfigDict(extra="forbid")

    work_item_id: str
    claim_id: str
    rule_id: str
    title: str
    recommended_action: str
    risk_band: Literal["high", "warning"]
    priority_score: int = Field(ge=0)
    status: WorkItemStatus
    assigned_to: str | None = None
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class WorkItemTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class QueueSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RepWorkItem]
    open_count: int = Field(ge=0)
    assigned_count: int = Field(ge=0)
