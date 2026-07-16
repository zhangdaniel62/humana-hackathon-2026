"""Shared session-state setup and deterministic ROI enforcement."""

from __future__ import annotations

from uuid import uuid4

from google.adk.tools import FunctionTool, ToolContext

from ..clients.member_records import MemberRecordsClient
from ..events import EventLog, event_log
from ..models import AgentEvent, EventType, MemberSessionContext, ROIStatus
from .roi_gatekeeper import check_roi_authorization

SESSION_ID_KEY = "session_id"
CALLER_NAME_KEY = "caller_name"
SUBJECT_MEMBER_ID_KEY = "subject_member_id"
ROI_STATUS_KEY = "roi_status"
ROI_FINDING_KEY = "roi_finding"
LANGUAGE_KEY = "language"
AGENT_FINDINGS_KEY = "agent_findings"
ROI_AGENT_KEY = "roi_gatekeeper"
INTENT_HISTORY_KEY = "intent_history"

ROI_ALLOWED = frozenset({ROIStatus.VERIFIED.value, ROIStatus.NOT_REQUIRED.value})


def roi_permits_member_detail(state: dict) -> bool:
    return state.get(ROI_STATUS_KEY) in ROI_ALLOWED


def roi_blocked_payload(state: dict) -> dict:
    finding = state.get(ROI_FINDING_KEY) or {}
    return {
        "status": "roi_required",
        "roi_status": state.get(ROI_STATUS_KEY, ROIStatus.UNKNOWN.value),
        "message": finding.get(
            "message",
            "Member-specific details cannot be shared until authorization is verified.",
        ),
    }


def record_intent(state: dict, intent: str) -> None:
    history = list(state.get(INTENT_HISTORY_KEY) or [])
    history.append(intent)
    state[INTENT_HISTORY_KEY] = history


def record_finding(state: dict, agent_key: str, payload: dict) -> None:
    findings = dict(state.get(AGENT_FINDINGS_KEY) or {})
    findings[agent_key] = payload
    state[AGENT_FINDINGS_KEY] = findings


def member_mismatch_payload(claim_id: str) -> dict:
    return {
        "status": "member_mismatch",
        "claim_id": claim_id,
        "message": (
            "That claim is not associated with the member established for this "
            "session. No claim details were disclosed."
        ),
    }


def build_establish_member_context_tool(
    client: MemberRecordsClient,
    events: EventLog | None = None,
) -> FunctionTool:
    """Build a tool that records shared context and resolves ROI."""

    resolved_events = events or event_log

    def establish_member_context(
        caller_name: str,
        subject_member_id: str,
        tool_context: ToolContext,
        language: str = "English",
    ) -> dict:
        """Establish caller/member context and verify disclosure authorization.

        Call this before any member-specific claim, readiness, or benefit lookup.
        The authenticated caller ID, when available, is read from session state.
        """

        state = tool_context.state
        session_id = str(state.get(SESSION_ID_KEY) or uuid4())
        first_context = not state.get("_session_started_emitted")
        normalized_caller = caller_name.strip()
        normalized_member = subject_member_id.strip().upper()
        normalized_language = language.strip() or "English"

        roi = check_roi_authorization(
            normalized_member,
            normalized_caller,
            caller_id=state.get("caller_id"),
            client=client,
        )
        context = MemberSessionContext(
            session_id=session_id,
            caller_name=normalized_caller,
            subject_member_id=normalized_member,
            language=normalized_language,
            roi=roi,
        )

        state[SESSION_ID_KEY] = session_id
        state[CALLER_NAME_KEY] = normalized_caller
        state[SUBJECT_MEMBER_ID_KEY] = normalized_member
        state[LANGUAGE_KEY] = normalized_language
        state[ROI_STATUS_KEY] = roi.status.value
        state[ROI_FINDING_KEY] = roi.model_dump(mode="json")
        state.setdefault(INTENT_HISTORY_KEY, [])
        record_finding(state, ROI_AGENT_KEY, roi.model_dump(mode="json"))
        record_intent(state, "establish_member_context")

        if first_context:
            resolved_events.publish_nowait(
                AgentEvent(
                    session_id=session_id,
                    agent="orchestrator",
                    event_type=EventType.SESSION_STARTED,
                    member_id=normalized_member,
                    payload={"synthetic": True},
                )
            )
            state["_session_started_emitted"] = True

        gap_key = (
            f"{normalized_member}:{normalized_caller.lower()}:{roi.status.value}"
        )
        if roi.status not in {ROIStatus.VERIFIED, ROIStatus.NOT_REQUIRED} and state.get(
            "_roi_gap_event_key"
        ) != gap_key:
            resolved_events.publish_nowait(
                AgentEvent(
                    session_id=session_id,
                    agent="roi_gatekeeper",
                    event_type=EventType.ROI_GAP_DETECTED,
                    member_id=normalized_member,
                    payload={
                        "roi_status": roi.status.value,
                        "reason": roi.reason,
                        "synthetic": True,
                    },
                )
            )
            state["_roi_gap_event_key"] = gap_key

        return context.model_dump(mode="json")

    return FunctionTool(establish_member_context)
