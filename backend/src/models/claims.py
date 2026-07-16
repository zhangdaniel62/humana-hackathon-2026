"""Typed BigQuery claim rows and claim-story agent contracts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class ClaimStatus(StrEnum):
    """Claim statuses currently present in the BigQuery claims table."""

    PAID = "Paid"
    PENDING = "Pending"
    IN_REVIEW = "In Review"
    DENIED = "Denied"


class ClaimTimelineEventType(StrEnum):
    """Lifecycle milestones derived from dates stored on a claim."""

    SERVICE = "service"
    SUBMITTED = "submitted"
    ADJUDICATION = "adjudication"


class ClaimStoryResultStatus(StrEnum):
    """Outcomes returned by the claim-story subagent."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    NEEDS_ESCALATION = "needs_escalation"


class ClaimRow(BaseModel):
    """One row from the live BigQuery ``claims`` table."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    member_id: str
    provider_id: str
    provider_name: str
    service_date: date
    submitted_date: date
    adjudication_date: date | None = None
    cpt_code: str
    cpt_description: str
    diagnosis_code: str
    claim_status: ClaimStatus
    denial_code: str | None = None
    denial_reason: str | None = None
    denial_fixable: bool | None = None
    billed_amount: float
    paid_amount: float
    referral_on_file: bool
    prior_auth_required: bool
    prior_auth_obtained: bool
    denial_risk_flag: bool
    modifier_mismatch: bool
    reprocessing_days_est: int | None = None

    @field_validator(
        "claim_id",
        "member_id",
        "provider_id",
        "provider_name",
        "cpt_code",
        "cpt_description",
        "diagnosis_code",
        mode="before",
    )
    @classmethod
    def normalize_required_strings(cls, value: object) -> object:
        """Trim required text fields without changing their stored meaning."""

        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("denial_code", "denial_reason", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object:
        """Treat blank optional strings as missing values."""

        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ClaimStoryRequest(BaseModel):
    """Input accepted by the standalone agent and an eventual ``AgentTool``."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(description="Exact claim identifier, for example CLM000001.")

    @field_validator("claim_id", mode="before")
    @classmethod
    def normalize_claim_id(cls, value: object) -> object:
        """Normalize claim identifiers so lookups are stable."""

        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("claim_id must not be blank")
        return normalized


class ClaimTimelineEvent(BaseModel):
    """A member-readable claim lifecycle milestone."""

    model_config = ConfigDict(extra="forbid")

    event_type: ClaimTimelineEventType
    event_date: date | None
    title: str
    explanation: str

    @field_serializer("event_date")
    def serialize_event_date(self, value: date | None) -> str | None:
        """Keep AgentTool function responses JSON serializable in ADK 2.4."""

        return value.isoformat() if value is not None else None


class DenialDetails(BaseModel):
    """Grounded denial facts and reviewed next-step guidance."""

    model_config = ConfigDict(extra="forbid")

    code: str
    reason: str
    fixable: bool
    required_actions: list[str]
    reprocessing_days_est: int | None = None


class GroundingReference(BaseModel):
    """The BigQuery record and fields used to construct a claim story."""

    model_config = ConfigDict(extra="forbid")

    table: str
    record_id: str
    fields_used: list[str]


class ClaimStory(BaseModel):
    """Structured facts plus a concise member-facing explanation."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    member_id: str
    current_status: ClaimStatus
    summary: str
    provider_name: str
    service_code: str
    service_description: str
    billed_amount: float
    paid_amount: float
    timeline: list[ClaimTimelineEvent]
    denial: DenialDetails | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    escalation_required: bool
    grounding: GroundingReference


class ClaimStoryResult(BaseModel):
    """Discriminated result returned by the claim-story subagent."""

    model_config = ConfigDict(extra="forbid")

    status: ClaimStoryResultStatus
    story: ClaimStory | None = None
    message: str

    @model_validator(mode="after")
    def validate_status_payload(self) -> ClaimStoryResult:
        """Keep result status and payload combinations unambiguous."""

        if self.status == ClaimStoryResultStatus.NOT_FOUND and self.story is not None:
            raise ValueError("not_found results must not contain a story")
        if self.status != ClaimStoryResultStatus.NOT_FOUND and self.story is None:
            raise ValueError(f"{self.status.value} results must contain a story")
        if (
            self.status == ClaimStoryResultStatus.SUCCESS
            and self.story is not None
            and self.story.escalation_required
        ):
            raise ValueError("success results cannot require escalation")
        if (
            self.status == ClaimStoryResultStatus.NEEDS_ESCALATION
            and self.story is not None
            and not self.story.escalation_required
        ):
            raise ValueError("needs_escalation results must require escalation")
        return self
