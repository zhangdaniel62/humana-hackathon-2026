"""Deterministic scanner tests over the reviewed readiness rules."""

from __future__ import annotations

from src.auth import AuthStore
from src.models import ClaimStatus
from src.prevention import PreventionScanner, PreventionStore
from tests.claim_fixtures import claim_for_status


class PopulationRepository:
    def __init__(self, claims):
        self.claims = {claim.claim_id: claim for claim in claims}

    def get_claim(self, claim_id):
        return self.claims.get(claim_id)

    def list_actionable_claims(self, *, limit=500):
        return [
            claim
            for claim in sorted(self.claims.values(), key=lambda row: row.claim_id)
            if claim.claim_status in {ClaimStatus.PENDING, ClaimStatus.IN_REVIEW}
        ][:limit]


def test_scanner_uses_only_eligible_claims_and_reviewed_factors(tmp_path) -> None:
    high = claim_for_status(ClaimStatus.PENDING).model_copy(
        update={
            "claim_id": "CLM100001",
            "prior_auth_required": True,
            "prior_auth_obtained": False,
            "referral_on_file": True,
            "denial_risk_flag": True,
            "modifier_mismatch": True,
        }
    )
    warning = claim_for_status(ClaimStatus.IN_REVIEW).model_copy(
        update={
            "claim_id": "CLM100002",
            "prior_auth_required": False,
            "prior_auth_obtained": False,
            "referral_on_file": False,
        }
    )
    denied = claim_for_status(ClaimStatus.DENIED).model_copy(
        update={"claim_id": "CLM100003"}
    )
    database = tmp_path / "scanner.sqlite3"
    AuthStore(database).initialize(enable_demo_seed=False)
    store = PreventionStore(database)
    store.initialize()
    scanner = PreventionScanner(PopulationRepository([warning, denied, high]), store)

    result = scanner.scan(idempotency_key="scan-1", source="manager")

    assert result.claims_scanned == 2
    assert result.items_created == 2
    with store._connect() as connection:
        rows = connection.execute(
            "SELECT claim_id, rule_id, priority_score FROM rep_work_items "
            "ORDER BY priority_score DESC, claim_id"
        ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("CLM100001", "MISSING_REQUIRED_PRIOR_AUTH", 100),
        ("CLM100002", "REFERRAL_ON_FILE_WARNING", 50),
    ]
