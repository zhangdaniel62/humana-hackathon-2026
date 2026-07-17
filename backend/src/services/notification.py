"""Grounded, deterministic notification previews for readiness findings."""

from __future__ import annotations

from ..models import ClaimReadinessAssessment
from ..models.operations import NotificationPreview


def build_notification_preview(
    assessment: ClaimReadinessAssessment,
) -> NotificationPreview:
    factors = [
        {
            "rule_id": factor.rule_id,
            "title": factor.title,
            "evidence": factor.evidence,
        }
        for factor in assessment.factors
    ]
    finding_text = "; ".join(factor.title for factor in assessment.factors)
    action_text = " ".join(assessment.recommended_actions)
    if not finding_text:
        finding_text = "no reviewed readiness rules matched"
    if not action_text:
        action_text = "Continue normal claim processing."

    return NotificationPreview(
        claim_id=assessment.claim_id,
        member_id=assessment.member_id,
        subject=f"Claim Readiness preview for {assessment.claim_id}",
        message=(
            f"Claim {assessment.claim_id} is {assessment.claim_status.value}. "
            f"The rules-based Claim Readiness screen found {finding_text}. "
            f"Recommended next step: {action_text}"
        ),
        evidence=factors,
        recommended_actions=assessment.recommended_actions,
        grounding=assessment.grounding.model_dump(mode="json"),
    )
