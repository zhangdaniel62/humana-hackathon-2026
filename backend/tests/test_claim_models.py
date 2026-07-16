"""Tests for claim row and agent contract validation."""

from __future__ import annotations

from datetime import date
import json
import unittest

from pydantic import ValidationError

from src.models.claims import (
    ClaimStoryRequest,
    ClaimTimelineEvent,
    ClaimTimelineEventType,
)
from tests.claim_fixtures import load_claim_rows


class ClaimModelTests(unittest.TestCase):
    def test_all_csv_claims_validate(self) -> None:
        claims = load_claim_rows()

        self.assertEqual(880, len(claims))
        self.assertEqual(880, len({claim.claim_id for claim in claims}))

    def test_request_normalizes_claim_id(self) -> None:
        request = ClaimStoryRequest(claim_id="  clm000001 ")

        self.assertEqual("CLM000001", request.claim_id)

    def test_request_rejects_blank_claim_id(self) -> None:
        with self.assertRaises(ValidationError):
            ClaimStoryRequest(claim_id="   ")

    def test_timeline_model_dump_is_json_serializable_for_adk_tools(self) -> None:
        event = ClaimTimelineEvent(
            event_type=ClaimTimelineEventType.SERVICE,
            event_date=date(2026, 1, 2),
            title="Service received",
            explanation="A service was provided.",
        )

        payload = event.model_dump()

        self.assertEqual("2026-01-02", payload["event_date"])
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
