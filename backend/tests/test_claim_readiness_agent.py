"""ADK wiring tests for the Claim Readiness tool."""

from __future__ import annotations

from src.agents.claim_readiness import (
    READINESS_AGENT_KEY,
    READINESS_STATE_KEY,
    build_screen_claim_readiness_tool,
)
from src.models import ClaimStatus
from src.services.claim_readiness import ClaimReadinessService
from tests.claim_fixtures import claim_for_status


class StaticRepository:
    def __init__(self, claim):
        self.claim = claim

    def get_claim(self, claim_id: str):
        return self.claim if claim_id == self.claim.claim_id else None


class StubContext:
    def __init__(self, **state) -> None:
        self.state = state


def test_tool_writes_structured_result_and_shared_finding() -> None:
    claim = claim_for_status(ClaimStatus.PENDING).model_copy(
        update={
            "referral_on_file": True,
            "prior_auth_required": True,
            "prior_auth_obtained": False,
        }
    )
    tool = build_screen_claim_readiness_tool(
        ClaimReadinessService(StaticRepository(claim))
    )
    context = StubContext()

    payload = tool.func(claim.claim_id.lower(), context)

    assert payload["assessment"]["risk_band"] == "high"
    assert context.state[READINESS_STATE_KEY] == payload
    assert context.state["agent_findings"][READINESS_AGENT_KEY] == payload


def test_guarded_tool_fails_closed_without_roi() -> None:
    claim = claim_for_status(ClaimStatus.PENDING)
    tool = build_screen_claim_readiness_tool(
        ClaimReadinessService(StaticRepository(claim)),
        enforce_member_context=True,
    )
    context = StubContext(subject_member_id=claim.member_id)

    payload = tool.func(claim.claim_id, context)

    assert payload["status"] == "roi_required"
    assert "assessment" not in payload
