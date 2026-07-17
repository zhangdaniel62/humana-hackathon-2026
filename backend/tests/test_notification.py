"""Notification previews remain grounded and explicitly unsent."""

from src.models import ClaimStatus
from src.services.claim_readiness import ClaimReadinessService
from src.services.notification import build_notification_preview
from tests.claim_fixtures import claim_for_status


class StaticRepository:
    def __init__(self, claim):
        self.claim = claim

    def get_claim(self, claim_id: str):
        return self.claim if claim_id == self.claim.claim_id else None


def test_preview_uses_only_readiness_evidence_and_is_not_sent() -> None:
    claim = claim_for_status(ClaimStatus.IN_REVIEW).model_copy(
        update={
            "referral_on_file": True,
            "prior_auth_required": True,
            "prior_auth_obtained": False,
        }
    )
    result = ClaimReadinessService(StaticRepository(claim)).screen(claim.claim_id)
    preview = build_notification_preview(result.assessment)

    assert preview.status == "preview"
    assert preview.delivery_status == "not_sent"
    assert preview.claim_id == claim.claim_id
    assert "Required prior authorization is missing" in preview.message
    assert preview.grounding["record_id"] == claim.claim_id
    assert claim.diagnosis_code not in preview.message
    assert str(claim.billed_amount) not in preview.message
