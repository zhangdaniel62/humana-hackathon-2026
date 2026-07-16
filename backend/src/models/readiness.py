"""Deterministic Claim Readiness request and result contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .claims import ClaimStatus, GroundingReference


class ClaimReadinessResultStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    INELIGIBLE = "ineligible"
    INCOMPLETE = "incomplete"


class ClaimReadinessRiskBand(StrEnum):
    HIGH = "high"
    WARNING = "warning"
    CLEAR = "clear"


class ReadinessFactorSeverity(StrEnum):
    HIGH = "high"
    WARNING = "warning"


class ClaimReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(description="Exact claim identifier, for example CLM000377.")

    @field_validator("claim_id", mode="before")
    @classmethod
    def normalize_claim_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("claim_id must not be blank")
        return normalized


class ReadinessFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    severity: ReadinessFactorSeverity
    title: str
    evidence: dict[str, Any]
    recommended_action: str


class DataCompleteness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    required_fields: list[str]
    missing_fields: list[str]


class ClaimReadinessAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    member_id: str
    claim_status: ClaimStatus
    risk_band: ClaimReadinessRiskBand
    summary: str
    factors: list[ReadinessFactor]
    recommended_actions: list[str]
    data_completeness: DataCompleteness
    grounding: GroundingReference
    methodology: Literal["reviewed_deterministic_rules"] = (
        "reviewed_deterministic_rules"
    )
    data_label: Literal["synthetic_demo_data"] = "synthetic_demo_data"


class ClaimReadinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ClaimReadinessResultStatus
    assessment: ClaimReadinessAssessment | None = None
    message: str
    data_completeness: DataCompleteness | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> ClaimReadinessResult:
        if self.status == ClaimReadinessResultStatus.SUCCESS:
            if self.assessment is None:
                raise ValueError("success results require an assessment")
        elif self.assessment is not None:
            raise ValueError(f"{self.status.value} results must not contain an assessment")
        if (
            self.status == ClaimReadinessResultStatus.INCOMPLETE
            and self.data_completeness is None
        ):
            raise ValueError("incomplete results require data_completeness")
        return self
