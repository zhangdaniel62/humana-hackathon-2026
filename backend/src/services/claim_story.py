"""Deterministic claim-story preparation and denial guidance."""

from __future__ import annotations

from dataclasses import dataclass

from ..clients.claims import ClaimsRepository
from ..models.claims import (
    ClaimRow,
    ClaimStatus,
    ClaimStory,
    ClaimStoryResult,
    ClaimStoryResultStatus,
    ClaimTimelineEvent,
    ClaimTimelineEventType,
    DenialDetails,
    GroundingReference,
)

CLAIM_STORY_CONFIDENCE_THRESHOLD = 0.80


@dataclass(frozen=True)
class DenialGuidance:
    """Reviewed actions associated with a known denial code."""

    required_actions: tuple[str, ...]


DENIAL_GUIDANCE: dict[str, DenialGuidance] = {
    "CO-109": DenialGuidance(
        ("Verify coordination of benefits and resubmit to the correct payer.",)
    ),
    "CO-11": DenialGuidance(
        ("Correct or support the diagnosis coding and resubmit the claim.",)
    ),
    "CO-16": DenialGuidance(
        ("Supply the missing claim information or supporting documentation.",)
    ),
    "CO-167": DenialGuidance(
        ("Verify coverage and submit a corrected claim or a supported appeal.",)
    ),
    "CO-29": DenialGuidance(
        ("Review timely-filing evidence and escalate the claim for an appeal.",)
    ),
    "CO-4": DenialGuidance(
        ("Correct the procedure and modifier combination, then resubmit.",)
    ),
    "CO-50": DenialGuidance(
        (
            "Verify the benefit exclusion and appeal only when coverage evidence "
            "supports the service.",
        )
    ),
    "CO-97": DenialGuidance(
        (
            "Review claim bundling and correct or appeal when the service is "
            "separately payable.",
        )
    ),
    "CO-B7": DenialGuidance(
        (
            "Verify provider eligibility and correct the billing provider or "
            "credentialing issue.",
        )
    ),
    "PR-1": DenialGuidance(
        ("Explain the deductible responsibility and verify the EOB if disputed.",)
    ),
}


class ClaimStoryService:
    """Build grounded claim stories without asking an LLM to invent facts."""

    def __init__(
        self,
        repository: ClaimsRepository,
        confidence_threshold: float = CLAIM_STORY_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.repository = repository
        self.confidence_threshold = confidence_threshold

    def prepare(self, claim_id: str) -> ClaimStoryResult:
        """Fetch an exact claim and return its deterministic story facts."""

        claim = self.repository.get_claim(claim_id)
        if claim is None:
            return ClaimStoryResult(
                status=ClaimStoryResultStatus.NOT_FOUND,
                story=None,
                message=f"No claim was found for {claim_id}.",
            )

        confidence, escalation_reasons = self._assess_confidence(claim)
        escalation_required = confidence < self.confidence_threshold
        story = ClaimStory(
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            current_status=claim.claim_status,
            summary=self._build_summary(claim, escalation_required),
            provider_name=claim.provider_name,
            service_code=claim.cpt_code,
            service_description=claim.cpt_description,
            billed_amount=claim.billed_amount,
            paid_amount=claim.paid_amount,
            timeline=self._build_timeline(claim),
            denial=self._build_denial_details(claim),
            confidence=confidence,
            escalation_required=escalation_required,
            grounding=self._build_grounding(claim),
        )

        if escalation_required:
            reason_text = "; ".join(escalation_reasons)
            return ClaimStoryResult(
                status=ClaimStoryResultStatus.NEEDS_ESCALATION,
                story=story,
                message=(
                    "The available claim data is not sufficient for a reliable "
                    f"self-service explanation: {reason_text}."
                ),
            )

        return ClaimStoryResult(
            status=ClaimStoryResultStatus.SUCCESS,
            story=story,
            message="The claim story was prepared from the BigQuery claim record.",
        )

    def _build_timeline(self, claim: ClaimRow) -> list[ClaimTimelineEvent]:
        timeline = [
            ClaimTimelineEvent(
                event_type=ClaimTimelineEventType.SERVICE,
                event_date=claim.service_date,
                title="Service received",
                explanation=(
                    f"{claim.cpt_description} ({claim.cpt_code}) was provided by "
                    f"{claim.provider_name}."
                ),
            ),
            ClaimTimelineEvent(
                event_type=ClaimTimelineEventType.SUBMITTED,
                event_date=claim.submitted_date,
                title="Claim submitted",
                explanation=(
                    f"The provider submitted a claim for ${claim.billed_amount:,.2f}."
                ),
            ),
        ]

        if claim.adjudication_date is not None:
            timeline.append(
                ClaimTimelineEvent(
                    event_type=ClaimTimelineEventType.ADJUDICATION,
                    event_date=claim.adjudication_date,
                    title="Claim status recorded",
                    explanation=self._adjudication_explanation(claim),
                )
            )
        return timeline

    def _adjudication_explanation(self, claim: ClaimRow) -> str:
        if claim.claim_status == ClaimStatus.PAID:
            return (
                f"The claim was processed as paid, with ${claim.paid_amount:,.2f} "
                "paid by the plan."
            )
        if claim.claim_status == ClaimStatus.DENIED:
            if claim.denial_code and claim.denial_reason:
                return (
                    f"The claim was denied under {claim.denial_code}: "
                    f"{claim.denial_reason}."
                )
            return "The claim was recorded as denied, but denial details are incomplete."
        if claim.claim_status == ClaimStatus.IN_REVIEW:
            return "The claim remains in review and does not yet have a final outcome."
        return "The current claim status was recorded by the plan."

    def _build_denial_details(self, claim: ClaimRow) -> DenialDetails | None:
        if claim.claim_status != ClaimStatus.DENIED:
            return None
        if (
            claim.denial_code is None
            or claim.denial_reason is None
            or claim.denial_fixable is None
        ):
            return None

        guidance = DENIAL_GUIDANCE.get(claim.denial_code)
        return DenialDetails(
            code=claim.denial_code,
            reason=claim.denial_reason,
            fixable=claim.denial_fixable,
            required_actions=(
                list(guidance.required_actions) if guidance is not None else []
            ),
            reprocessing_days_est=(
                claim.reprocessing_days_est if claim.denial_fixable else None
            ),
        )

    def _assess_confidence(self, claim: ClaimRow) -> tuple[float, list[str]]:
        confidence = 1.0
        reasons: list[str] = []

        if claim.claim_status == ClaimStatus.PAID and claim.adjudication_date is None:
            confidence -= 0.25
            reasons.append("paid claim is missing its adjudication date")

        if claim.claim_status == ClaimStatus.DENIED:
            if claim.adjudication_date is None:
                confidence -= 0.15
                reasons.append("denied claim is missing its adjudication date")
            if claim.denial_code is None:
                confidence -= 0.25
                reasons.append("denial code is missing")
            elif claim.denial_code not in DENIAL_GUIDANCE:
                confidence -= 0.50
                reasons.append(f"denial code {claim.denial_code} is unsupported")
            if claim.denial_reason is None:
                confidence -= 0.25
                reasons.append("denial reason is missing")
            if claim.denial_fixable is None:
                confidence -= 0.25
                reasons.append("denial fixability is missing")
            elif claim.denial_fixable and claim.reprocessing_days_est is None:
                confidence -= 0.25
                reasons.append("fixable denial is missing a reprocessing estimate")

        return max(0.0, round(confidence, 2)), reasons

    def _build_summary(self, claim: ClaimRow, escalation_required: bool) -> str:
        if escalation_required:
            return (
                f"Claim {claim.claim_id} is marked {claim.claim_status.value}, but "
                "some required details need review by a claims specialist."
            )
        if claim.claim_status == ClaimStatus.PAID:
            return (
                f"Claim {claim.claim_id} was paid. The plan paid "
                f"${claim.paid_amount:,.2f} toward the submitted "
                f"${claim.billed_amount:,.2f} charge."
            )
        if claim.claim_status == ClaimStatus.PENDING:
            return (
                f"Claim {claim.claim_id} is pending and has not reached a final "
                "adjudication outcome."
            )
        if claim.claim_status == ClaimStatus.IN_REVIEW:
            return (
                f"Claim {claim.claim_id} is still under review and does not yet "
                "have a final payment or denial outcome."
            )

        denial = self._build_denial_details(claim)
        if denial is None:
            return (
                f"Claim {claim.claim_id} was denied, but the available denial "
                "details are incomplete."
            )
        if denial.fixable and denial.reprocessing_days_est is not None:
            return (
                f"Claim {claim.claim_id} was denied for {denial.reason.lower()}. "
                f"The issue is marked fixable, with an estimated "
                f"{denial.reprocessing_days_est}-day reprocessing time after "
                "correction."
            )
        return (
            f"Claim {claim.claim_id} was denied for {denial.reason.lower()}. "
            "The record does not identify this denial as fixable."
        )

    def _build_grounding(self, claim: ClaimRow) -> GroundingReference:
        fields = [
            "claim_id",
            "member_id",
            "provider_id",
            "provider_name",
            "service_date",
            "submitted_date",
            "adjudication_date",
            "cpt_code",
            "cpt_description",
            "claim_status",
            "billed_amount",
            "paid_amount",
        ]
        if claim.claim_status == ClaimStatus.DENIED:
            fields.extend(
                [
                    "denial_code",
                    "denial_reason",
                    "denial_fixable",
                    "reprocessing_days_est",
                ]
            )
        return GroundingReference(
            table="claims",
            record_id=claim.claim_id,
            fields_used=fields,
        )
