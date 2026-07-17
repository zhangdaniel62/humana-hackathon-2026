"""In-process read-only projection of structured ADK session findings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..models.operations import SessionSummary


class SessionSummaryStore:
    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}

    def capture(self, state: dict[str, Any]) -> None:
        session_id = state.get("session_id")
        if session_id:
            self._states[str(session_id)] = deepcopy(dict(state))

    def get(self, session_id: str) -> SessionSummary | None:
        state = self._states.get(session_id)
        if state is None:
            return None
        findings = state.get("agent_findings") or {}
        required = {
            "roi": findings.get("roi_gatekeeper") or state.get("roi_finding"),
            "claim": findings.get("claim_story"),
            "benefits": findings.get("benefits_qa"),
            "readiness": findings.get("claim_readiness"),
        }
        missing = [name for name, value in required.items() if value is None]
        preview = findings.get("notification_preview")
        return SessionSummary(
            session_id=session_id,
            status="incomplete" if missing else "ready",
            caller_name=state.get("caller_name"),
            subject_member_id=state.get("subject_member_id"),
            language=state.get("language"),
            **required,
            notification_preview=preview,
            intent_history=list(state.get("intent_history") or []),
            missing_findings=missing,
        )

    def clear(self) -> None:
        self._states.clear()


session_summary_store = SessionSummaryStore()

