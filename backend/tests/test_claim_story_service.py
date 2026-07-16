"""Tests for deterministic claim-story preparation."""

from __future__ import annotations

import unittest

from src.models.claims import ClaimRow, ClaimStatus, ClaimStoryResultStatus
from src.services.claim_story import DENIAL_GUIDANCE, ClaimStoryService
from tests.claim_fixtures import claim_for_status, load_claim_rows


class StaticClaimsRepository:
    def __init__(self, claims: list[ClaimRow]) -> None:
        self.claims = {claim.claim_id: claim for claim in claims}

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        return self.claims.get(claim_id)


class ClaimStoryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.claims = load_claim_rows()

    def service_for(self, *claims: ClaimRow) -> ClaimStoryService:
        return ClaimStoryService(StaticClaimsRepository(list(claims)))

    def test_not_found_result(self) -> None:
        result = self.service_for().prepare("CLM999999")

        self.assertEqual(ClaimStoryResultStatus.NOT_FOUND, result.status)
        self.assertIsNone(result.story)

    def test_timeline_for_each_status(self) -> None:
        for status in ClaimStatus:
            with self.subTest(status=status):
                claim = claim_for_status(status)
                result = self.service_for(claim).prepare(claim.claim_id)

                self.assertEqual(ClaimStoryResultStatus.SUCCESS, result.status)
                self.assertIsNotNone(result.story)
                assert result.story is not None
                event_types = [event.event_type.value for event in result.story.timeline]
                self.assertEqual(["service", "submitted"], event_types[:2])
                if claim.adjudication_date is None:
                    self.assertEqual(2, len(event_types))
                else:
                    self.assertEqual("adjudication", event_types[-1])
                if status == ClaimStatus.DENIED:
                    self.assertIsNotNone(result.story.denial)
                else:
                    self.assertIsNone(result.story.denial)

    def test_all_observed_denial_codes_have_reviewed_guidance(self) -> None:
        denied_claims = [
            claim for claim in self.claims if claim.claim_status == ClaimStatus.DENIED
        ]
        observed_codes = {claim.denial_code for claim in denied_claims}

        self.assertEqual(set(DENIAL_GUIDANCE), observed_codes)
        for claim in denied_claims:
            with self.subTest(claim_id=claim.claim_id):
                result = self.service_for(claim).prepare(claim.claim_id)
                self.assertEqual(ClaimStoryResultStatus.SUCCESS, result.status)
                assert result.story is not None
                assert result.story.denial is not None
                self.assertTrue(result.story.denial.required_actions)

    def test_fixable_denials_preserve_eta(self) -> None:
        fixable = next(
            claim
            for claim in self.claims
            if claim.claim_status == ClaimStatus.DENIED and claim.denial_fixable
        )
        result = self.service_for(fixable).prepare(fixable.claim_id)

        assert result.story is not None
        assert result.story.denial is not None
        self.assertEqual(
            fixable.reprocessing_days_est,
            result.story.denial.reprocessing_days_est,
        )

    def test_nonfixable_denials_do_not_invent_eta(self) -> None:
        nonfixable = next(
            claim
            for claim in self.claims
            if claim.claim_status == ClaimStatus.DENIED
            and claim.denial_fixable is False
        )
        result = self.service_for(nonfixable).prepare(nonfixable.claim_id)

        assert result.story is not None
        assert result.story.denial is not None
        self.assertIsNone(result.story.denial.reprocessing_days_est)

    def test_unknown_denial_code_requires_escalation(self) -> None:
        denied = claim_for_status(ClaimStatus.DENIED)
        unknown = denied.model_copy(update={"denial_code": "CO-999"})
        result = self.service_for(unknown).prepare(unknown.claim_id)

        self.assertEqual(ClaimStoryResultStatus.NEEDS_ESCALATION, result.status)
        assert result.story is not None
        self.assertTrue(result.story.escalation_required)
        self.assertLess(result.story.confidence, 0.80)
        assert result.story.denial is not None
        self.assertEqual([], result.story.denial.required_actions)

    def test_missing_denial_evidence_requires_escalation(self) -> None:
        denied = claim_for_status(ClaimStatus.DENIED)
        incomplete = denied.model_copy(update={"denial_reason": None})
        result = self.service_for(incomplete).prepare(incomplete.claim_id)

        self.assertEqual(ClaimStoryResultStatus.NEEDS_ESCALATION, result.status)
        assert result.story is not None
        self.assertTrue(result.story.escalation_required)
        self.assertIsNone(result.story.denial)

    def test_fixable_denial_without_eta_requires_escalation(self) -> None:
        denied = next(
            claim
            for claim in self.claims
            if claim.claim_status == ClaimStatus.DENIED and claim.denial_fixable
        )
        incomplete = denied.model_copy(update={"reprocessing_days_est": None})
        result = self.service_for(incomplete).prepare(incomplete.claim_id)

        self.assertEqual(ClaimStoryResultStatus.NEEDS_ESCALATION, result.status)
        assert result.story is not None
        self.assertEqual(0.75, result.story.confidence)


if __name__ == "__main__":
    unittest.main()
