"""ADK tool exposing the deterministic Claim Readiness service."""

from __future__ import annotations

from google.adk.tools import FunctionTool, ToolContext

from ..events import EventLog, event_log
from ..models import (
    AgentEvent,
    ClaimReadinessRequest,
    ClaimReadinessResult,
    EventType,
)
from ..services.claim_readiness import ClaimReadinessService
from ..services.notification import build_notification_preview
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
NOTIFICATION_AGENT_KEY = "notification_preview"
INTERVENTION_AGENT_KEY = "corrective_intervention"


def build_screen_claim_readiness_tool(
    service: ClaimReadinessService,
    *,
    enforce_member_context: bool = False,
    events: EventLog | None = None,
) -> FunctionTool:
    """Build the standalone exact-claim readiness tool."""

    resolved_events = events or event_log

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
            assessment = result.assessment
            if assessment is not None and assessment.factors:
                preview = build_notification_preview(assessment)
                preview_payload = preview.model_dump(mode="json")
                payload["notification_preview"] = preview_payload
                record_finding(
                    tool_context.state, NOTIFICATION_AGENT_KEY, preview_payload
                )
                session_id = tool_context.state.get("session_id")
                if session_id:
                    for factor in assessment.factors:
                        event_payload = {
                            "rule_id": factor.rule_id,
                            "evidence": factor.evidence,
                            "recommended_action": factor.recommended_action,
                            "event_source": "claim_readiness_tool",
                            "synthetic": True,
                            "risk_band": assessment.risk_band.value,
                            "notification_preview_id": str(preview.preview_id),
                        }
                        resolved_events.publish_nowait(
                            AgentEvent(
                                session_id=str(session_id),
                                agent=READINESS_AGENT_KEY,
                                event_type=EventType.DENIAL_RISK_DETECTED,
                                member_id=assessment.member_id,
                                claim_id=assessment.claim_id,
                                payload=event_payload,
                            )
                        )
                        resolved_events.publish_nowait(
                            AgentEvent(
                                session_id=str(session_id),
                                agent=READINESS_AGENT_KEY,
                                event_type=EventType.INTERVENTION_RECOMMENDED,
                                member_id=assessment.member_id,
                                claim_id=assessment.claim_id,
                                payload=event_payload,
                            )
                        )
        tool_context.state[READINESS_STATE_KEY] = payload
        record_finding(tool_context.state, READINESS_AGENT_KEY, payload)
        record_intent(tool_context.state, READINESS_AGENT_KEY)
        return payload

    return FunctionTool(screen_claim_readiness)


def build_record_corrective_intervention_tool(
    *, events: EventLog | None = None,
) -> FunctionTool:
    """Build a tool that records, but does not claim the outcome of, an action."""

    resolved_events = events or event_log

    def record_corrective_intervention(
        claim_id: str,
        tool_context: ToolContext,
        action: str = "",
    ) -> dict:
        """Record a reviewed corrective action for the latest readiness result.

        The action must match one recommended by the rules-based readiness result.
        This records an intervention; it does not claim that a denial was prevented.
        """

        normalized_claim_id = ClaimReadinessRequest(claim_id=claim_id).claim_id
        readiness_payload = tool_context.state.get(READINESS_STATE_KEY) or {}
        assessment_payload = readiness_payload.get("assessment")
        if (
            not assessment_payload
            or assessment_payload.get("claim_id") != normalized_claim_id
        ):
            return {
                "status": "readiness_required",
                "claim_id": normalized_claim_id,
                "message": (
                    "Run Claim Readiness for this exact claim before recording "
                    "an intervention."
                ),
            }

        assessment = ClaimReadinessResult.model_validate(
            {
                key: value
                for key, value in readiness_payload.items()
                if key != "notification_preview"
            }
        ).assessment
        assert assessment is not None
        recommended = assessment.recommended_actions
        selected_action = action.strip() or (recommended[0] if recommended else "")
        if not selected_action or selected_action not in recommended:
            return {
                "status": "unsupported_action",
                "claim_id": normalized_claim_id,
                "recommended_actions": recommended,
                "message": (
                    "Only an action grounded in the readiness result can be recorded."
                ),
            }

        factor = next(
            item
            for item in assessment.factors
            if item.recommended_action == selected_action
        )
        payload = {
            "status": "recorded",
            "claim_id": assessment.claim_id,
            "member_id": assessment.member_id,
            "rule_id": factor.rule_id,
            "action": selected_action,
            "synthetic": True,
            "causal_claim": "none",
            "message": "Corrective intervention recorded; no claim outcome is asserted.",
        }
        event_key = f"{assessment.claim_id}:{factor.rule_id}:{selected_action}"
        emitted = set(tool_context.state.get("_recorded_intervention_keys") or [])
        if event_key not in emitted:
            resolved_events.publish_nowait(
                AgentEvent(
                    session_id=str(
                        tool_context.state.get("session_id") or "unknown"
                    ),
                    agent=INTERVENTION_AGENT_KEY,
                    event_type=EventType.INTERVENTION_RECORDED,
                    member_id=assessment.member_id,
                    claim_id=assessment.claim_id,
                    payload={
                        "rule_id": factor.rule_id,
                        "evidence": factor.evidence,
                        "recommended_action": factor.recommended_action,
                        "event_source": "record_corrective_intervention_tool",
                        "synthetic": True,
                        "risk_band": assessment.risk_band.value,
                        "action": selected_action,
                    },
                )
            )
            emitted.add(event_key)
            tool_context.state["_recorded_intervention_keys"] = sorted(emitted)
        record_finding(tool_context.state, INTERVENTION_AGENT_KEY, payload)
        record_intent(tool_context.state, INTERVENTION_AGENT_KEY)
        return payload

    return FunctionTool(record_corrective_intervention)
