"""Tests for claim row and agent contract validation."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.models.claims import ClaimStoryRequest
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


if __name__ == "__main__":
    unittest.main()
