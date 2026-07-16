"""ADK function tools: the only place session state meets the pure core.

`member_id` is read from session state rather than accepted as an argument, so
the model cannot invent or substitute one. Everything factual is computed by
answer.py; these functions only marshal.
"""

from typing import Any

from google.adk.tools import ToolContext

from . import events
from .answer import answer_benefits_question
from .contract import (
    AGENT_KEY,
    EVENT_TYPE,
    NETWORK_GAP_EVENT,
    StateKeys,
    roi_permits_detail,
)
from .loader import load_members
from .models import BenefitsAnswer, Resolution
from .providers import find_provider as _find_provider

_STATUS = {
    Resolution.RESOLVED: "ok",
    Resolution.AMBIGUOUS: "ambiguous",
    Resolution.NOT_FOUND: "not_found",
    Resolution.UNKNOWN_CODE: "unknown_code",
}


def _record(tool_context: ToolContext, answer: BenefitsAnswer) -> None:
    """Stash the deterministic answer so the card is assembled from data, not prose."""
    tool_context.state[StateKeys.LAST_LOOKUP] = answer.model_dump(mode="json")

    findings = dict(tool_context.state.get(StateKeys.AGENT_FINDINGS) or {})
    findings[AGENT_KEY] = answer.model_dump(mode="json")
    tool_context.state[StateKeys.AGENT_FINDINGS] = findings


def lookup_coverage(service_query: str, tool_context: ToolContext) -> dict[str, Any]:
    """Look up how a medical service is covered for the member in this session.

    Call this before answering ANY coverage, prior-authorization, or cost
    question. It is the only source of coverage truth.

    Args:
        service_query: The service as the caller described it, in their own words
            (for example "colonoscopy", "knee surgery", "MRI", or a CPT code such
            as "45378"). Pass the caller's phrasing; do not translate it into a
            code yourself.

    Returns:
        dict with `status` (one of "ok", "ambiguous", "not_found",
        "unknown_code", "roi_required", "no_member"), a ready-to-deliver
        `answer_text`, and the grounded facts: covered, prior_auth_required,
        cost, next_step, providers, grounded_on, plan_type.
    """
    member_id = tool_context.state.get(StateKeys.SUBJECT_MEMBER_ID)
    roi_status = tool_context.state.get(StateKeys.ROI_STATUS, "not_required")

    if not member_id:
        return {
            "status": "no_member",
            "answer_text": (
                "I need to know which member this is about before I can check "
                "plan-specific coverage."
            ),
        }

    answer = answer_benefits_question(service_query, member_id=member_id, roi_status=roi_status)
    _record(tool_context, answer)

    if not roi_permits_detail(roi_status):
        events.emit(
            EVENT_TYPE,
            {
                "session_id": tool_context.state.get(StateKeys.SESSION_ID),
                "member_id": member_id,
                "match_type": "refused_roi",
                "roi_status": roi_status,
            },
        )
        return {"status": "roi_required", "answer_text": answer.answer_text}

    payload = answer.model_dump(mode="json", exclude_none=False)
    payload["status"] = _STATUS[answer.resolution]

    events.emit(
        EVENT_TYPE,
        {
            "session_id": tool_context.state.get(StateKeys.SESSION_ID),
            "member_id": member_id,
            "cpt_code": answer.cpt_code,
            "matched_rule_id": answer.grounded_on[0] if answer.grounded_on else None,
            "plan_type": answer.plan_type,
            "match_type": answer.resolution.value,
            "answered_in_language": answer.language,
        },
    )
    return payload


def find_provider(service_or_cpt: str, tool_context: ToolContext) -> dict[str, Any]:
    """Find in-network providers who can perform a service for this member.

    Use when the service needs prior authorization, or when the caller asks where
    they can get it done.

    Args:
        service_or_cpt: The service in plain words or as a CPT code
            (for example "colonoscopy" or "45378").

    Returns:
        dict with `status`, `providers` (never empty), `basis` describing which
        fallback was used, `specialty_availability`, and a `note` to relay.
    """
    member_id = tool_context.state.get(StateKeys.SUBJECT_MEMBER_ID)
    if not member_id:
        return {"status": "no_member", "providers": []}

    result = _find_provider(service_or_cpt, member_id)

    # A specialty that is in-network but has nobody accepting new patients is a
    # network-adequacy finding -- Sentinel's beat. One line, real compliance value.
    if result.specialty_availability == "none_accepting_new_patients":
        events.emit(
            NETWORK_GAP_EVENT,
            {
                "session_id": tool_context.state.get(StateKeys.SESSION_ID),
                "member_id": member_id,
                "specialty": result.specialty_requested,
                "member_state": load_members()[member_id].state,
                "detail": (
                    f"No in-network {result.specialty_requested} providers are "
                    "accepting new patients."
                ),
            },
        )

    payload = result.model_dump(mode="json")
    payload["status"] = "ok"
    return payload
