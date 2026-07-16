"""ADK tool exposing the deterministic Claim Readiness service."""

from __future__ import annotations

from google.adk.tools import FunctionTool, ToolContext

from ..models import ClaimReadinessRequest
from ..services.claim_readiness import ClaimReadinessService
from .session_context import (
    SUBJECT_MEMBER_ID_KEY,
    member_mismatch_payload,
    record_finding,
    record_intent,
    roi_blocked_payload,
    roi_permits_member_detail,
)

READINESS_STATE_KEY = "readiness.result"
READINESS_AGENT_KEY = "claim_readiness"


def build_screen_claim_readiness_tool(
    service: ClaimReadinessService,
    *,
    enforce_member_context: bool = False,
) -> FunctionTool:
    """Build the standalone exact-claim readiness tool."""

    def screen_claim_readiness(
        claim_id: str,
        tool_context: ToolContext,
    ) -> dict:
        """Screen one exact claim for reviewed readiness risks.

        Use only for Pending or In Review claims. This is a rules classification,
        not a trained prediction or probability.
        """

        if enforce_member_context and not roi_permits_member_detail(tool_context.state):
            payload = roi_blocked_payload(tool_context.state)
            tool_context.state[READINESS_STATE_KEY] = payload
            record_finding(tool_context.state, READINESS_AGENT_KEY, payload)
            record_intent(tool_context.state, READINESS_AGENT_KEY)
            return payload

        request = ClaimReadinessRequest(claim_id=claim_id)
        result = service.screen(request.claim_id)
        if (
            enforce_member_context
            and result.assessment is not None
            and result.assessment.member_id
            != tool_context.state.get(SUBJECT_MEMBER_ID_KEY)
        ):
            payload = member_mismatch_payload(request.claim_id)
        else:
            payload = result.model_dump(mode="json")
        tool_context.state[READINESS_STATE_KEY] = payload
        record_finding(tool_context.state, READINESS_AGENT_KEY, payload)
        record_intent(tool_context.state, READINESS_AGENT_KEY)
        return payload

    return FunctionTool(screen_claim_readiness)
