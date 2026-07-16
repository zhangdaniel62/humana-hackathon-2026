"""Deterministic rules-based Claim Readiness screening."""

from __future__ import annotations

from ..clients.claims import ClaimsRepository
from ..models.claims import ClaimRow, ClaimStatus, GroundingReference
from ..models.readiness import (
    ClaimReadinessAssessment,
    ClaimReadinessResult,
    ClaimReadinessResultStatus,
    ClaimReadinessRiskBand,
    DataCompleteness,
    ReadinessFactor,
    ReadinessFactorSeverity,
)

ELIGIBLE_STATUSES = frozenset({ClaimStatus.PENDING, ClaimStatus.IN_REVIEW})

READINESS_REQUIRED_FIELDS = (
    "claim_id",
    "member_id",
    "claim_status",
    "cpt_code",
    "cpt_description",
    "referral_on_file",
    "prior_auth_required",
    "prior_auth_obtained",
    "denial_risk_flag",
    "modifier_mismatch",
)

MISSING_PRIOR_AUTH_RULE = "MISSING_REQUIRED_PRIOR_AUTH"
REFERRAL_WARNING_RULE = "REFERRAL_ON_FILE_WARNING"
MISSING_REFERRAL_WARNING = REFERRAL_WARNING_RULE


class ClaimReadinessService:
    """Screen one exact claim using reviewed, deterministic rules."""

    def __init__(self, repository: ClaimsRepository) -> None:
        self.repository = repository

    def evaluate(self, claim_id: str) -> ClaimReadinessResult:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            return ClaimReadinessResult(
                status=ClaimReadinessResultStatus.NOT_FOUND,
                message=f"No claim was found for {claim_id}.",
            )

        completeness = self._data_completeness(claim)
        if completeness.missing_fields:
            return ClaimReadinessResult(
                status=ClaimReadinessResultStatus.INCOMPLETE,
                message=(
                    "The synthetic claim record is missing fields required for a "
                    "trustworthy Claim Readiness screen. A claims specialist should "
                    "review it."
                ),
                data_completeness=completeness,
            )

        if claim.claim_status not in ELIGIBLE_STATUSES:
            return ClaimReadinessResult(
                status=ClaimReadinessResultStatus.INELIGIBLE,
                message=(
                    f"Claim {claim.claim_id} is {claim.claim_status.value}. Claim "
                    "Readiness applies only to Pending or In Review claims."
                ),
                data_completeness=completeness,
            )

        factors = self._factors(claim)
        risk_band = self._risk_band(factors)
        actions = list(
            dict.fromkeys(factor.recommended_action for factor in factors)
        )
        assessment = ClaimReadinessAssessment(
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            claim_status=claim.claim_status,
            risk_band=risk_band,
            summary=self._summary(claim, risk_band),
            factors=factors,
            recommended_actions=actions,
            data_completeness=completeness,
            grounding=GroundingReference(
                table="claims",
                record_id=claim.claim_id,
                fields_used=list(READINESS_REQUIRED_FIELDS),
            ),
        )
        return ClaimReadinessResult(
            status=ClaimReadinessResultStatus.SUCCESS,
            assessment=assessment,
            message=(
                "Claim Readiness was evaluated from the synthetic claim record "
                "using reviewed deterministic rules."
            ),
        )

    def screen(self, claim_id: str) -> ClaimReadinessResult:
        """Compatibility name used by the ADK tool layer."""

        return self.evaluate(claim_id)

    def _data_completeness(self, claim: ClaimRow) -> DataCompleteness:
        missing = [
            field
            for field in READINESS_REQUIRED_FIELDS
            if getattr(claim, field, None) is None
            or (
                isinstance(getattr(claim, field, None), str)
                and not getattr(claim, field).strip()
            )
        ]
        score = round(
            (len(READINESS_REQUIRED_FIELDS) - len(missing))
            / len(READINESS_REQUIRED_FIELDS),
            2,
        )
        return DataCompleteness(
            score=score,
            required_fields=list(READINESS_REQUIRED_FIELDS),
            missing_fields=missing,
        )

    def _factors(self, claim: ClaimRow) -> list[ReadinessFactor]:
        factors: list[ReadinessFactor] = []
        if claim.prior_auth_required and not claim.prior_auth_obtained:
            factors.append(
                ReadinessFactor(
                    rule_id=MISSING_PRIOR_AUTH_RULE,
                    severity=ReadinessFactorSeverity.HIGH,
                    title="Required prior authorization is missing",
                    evidence={
                        "prior_auth_required": True,
                        "prior_auth_obtained": False,
                        "cpt_code": claim.cpt_code,
                    },
                    recommended_action=(
                        "Confirm the required prior authorization with the provider "
                        "and attach it before final adjudication."
                    ),
                )
            )

        if not claim.referral_on_file:
            factors.append(
                ReadinessFactor(
                    rule_id=REFERRAL_WARNING_RULE,
                    severity=ReadinessFactorSeverity.WARNING,
                    title="Referral is not on file",
                    evidence={
                        "referral_on_file": False,
                        "cpt_code": claim.cpt_code,
                    },
                    recommended_action=(
                        "Confirm whether a referral is required under a reviewed "
                        "plan and service rule before final adjudication."
                    ),
                )
            )
        return factors

    def _risk_band(
        self, factors: list[ReadinessFactor]
    ) -> ClaimReadinessRiskBand:
        if any(
            factor.severity == ReadinessFactorSeverity.HIGH
            for factor in factors
        ):
            return ClaimReadinessRiskBand.HIGH
        if factors:
            return ClaimReadinessRiskBand.WARNING
        return ClaimReadinessRiskBand.CLEAR

    def _summary(
        self, claim: ClaimRow, risk_band: ClaimReadinessRiskBand
    ) -> str:
        prefix = (
            f"Synthetic demo claim {claim.claim_id} received a "
            f"{risk_band.value} rules classification"
        )
        if risk_band == ClaimReadinessRiskBand.HIGH:
            return f"{prefix} because required prior authorization is missing."
        if risk_band == ClaimReadinessRiskBand.WARNING:
            return (
                f"{prefix} because a referral is not on file; this is a workflow "
                "warning, not proof that a referral is required."
            )
        return (
            f"{prefix}; none of the reviewed Claim Readiness rules matched. "
            "This is not a prediction of the claim outcome."
        )
