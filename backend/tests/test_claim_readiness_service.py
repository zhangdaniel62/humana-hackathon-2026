"""Focused tests for the standalone deterministic Claim Readiness service."""

from __future__ import annotations

from src.models import (
    ClaimReadinessResultStatus,
    ClaimReadinessRiskBand,
    ClaimRow,
    ClaimStatus,
)
from src.services.claim_readiness import (
    MISSING_PRIOR_AUTH_RULE,
    MISSING_REFERRAL_WARNING,
    ClaimReadinessService,
)
from tests.claim_fixtures import claim_for_status


class StaticClaimsRepository:
    def __init__(self, claims: list[ClaimRow]) -> None:
        self.claims = {claim.claim_id: claim for claim in claims}

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        return self.claims.get(claim_id)


def service_for(*claims: ClaimRow) -> ClaimReadinessService:
    return ClaimReadinessService(StaticClaimsRepository(list(claims)))


def eligible_claim(**updates) -> ClaimRow:
    base = claim_for_status(ClaimStatus.PENDING)
    defaults = {
        "referral_on_file": True,
        "prior_auth_required": True,
        "prior_auth_obtained": True,
        "denial_risk_flag": False,
    }
    defaults.update(updates)
    return base.model_copy(update=defaults)


def test_high_risk_when_required_prior_authorization_is_missing() -> None:
    claim = eligible_claim(
        prior_auth_obtained=False,
        denial_risk_flag=True,
    )

    result = service_for(claim).screen(claim.claim_id)

    assert result.status == ClaimReadinessResultStatus.SUCCESS
    assert result.assessment is not None
    assert result.assessment.risk_band == ClaimReadinessRiskBand.HIGH
    assert [factor.rule_id for factor in result.assessment.factors] == [
        MISSING_PRIOR_AUTH_RULE
    ]


def test_denial_risk_flag_is_not_double_counted() -> None:
    claim = eligible_claim(
        prior_auth_obtained=False,
        denial_risk_flag=True,
    )

    result = service_for(claim).screen(claim.claim_id)

    assert result.assessment is not None
    assert len(result.assessment.factors) == 1


def test_clear_when_supported_rules_find_no_issue() -> None:
    claim = eligible_claim()

    result = service_for(claim).screen(claim.claim_id)

    assert result.status == ClaimReadinessResultStatus.SUCCESS
    assert result.assessment is not None
    assert result.assessment.risk_band == ClaimReadinessRiskBand.CLEAR
    assert result.assessment.factors == []
    assert result.assessment.data_completeness.score == 1.0


def test_missing_referral_is_a_warning_not_high_risk() -> None:
    claim = eligible_claim(referral_on_file=False)

    result = service_for(claim).screen(claim.claim_id)

    assert result.assessment is not None
    assert result.assessment.risk_band == ClaimReadinessRiskBand.WARNING
    assert [factor.rule_id for factor in result.assessment.factors] == [
        MISSING_REFERRAL_WARNING
    ]


def test_finalized_claim_is_ineligible() -> None:
    claim = claim_for_status(ClaimStatus.PAID)

    result = service_for(claim).screen(claim.claim_id)

    assert result.status == ClaimReadinessResultStatus.INELIGIBLE
    assert result.assessment is None


def test_incomplete_claim_fails_without_classification() -> None:
    claim = eligible_claim(member_id="")

    result = service_for(claim).screen(claim.claim_id)

    assert result.status == ClaimReadinessResultStatus.INCOMPLETE
    assert result.assessment is None
    assert result.data_completeness is not None
    assert result.data_completeness.missing_fields == ["member_id"]


def test_not_found_is_explicit() -> None:
    result = service_for().screen("CLM999999")

    assert result.status == ClaimReadinessResultStatus.NOT_FOUND
    assert result.assessment is None
