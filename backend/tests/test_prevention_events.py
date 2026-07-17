"""Typed readiness-event and corrective-intervention checkpoint tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agents.claim_readiness import (
    build_record_corrective_intervention_tool,
    build_screen_claim_readiness_tool,
)
from src.events import EventLog
from src.models import AgentEvent, ClaimStatus, EventType
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


def test_readiness_and_recorded_action_emit_auditable_correlated_events() -> None:
    claim = claim_for_status(ClaimStatus.PENDING).model_copy(
        update={
            "referral_on_file": True,
            "prior_auth_required": True,
            "prior_auth_obtained": False,
        }
    )
    events = EventLog()
    context = StubContext(
        session_id="session-1",
        subject_member_id=claim.member_id,
        roi_status="verified",
    )
    readiness_tool = build_screen_claim_readiness_tool(
        ClaimReadinessService(StaticRepository(claim)),
        enforce_member_context=True,
        events=events,
    )
    record_tool = build_record_corrective_intervention_tool(events=events)

    readiness = readiness_tool.func(claim.claim_id, context)
    recorded = record_tool.func(claim.claim_id, context)

    assert readiness["notification_preview"]["delivery_status"] == "not_sent"
    assert recorded["status"] == "recorded"
    assert [event.event_type for event in events.events] == [
        EventType.DENIAL_RISK_DETECTED,
        EventType.INTERVENTION_RECOMMENDED,
        EventType.INTERVENTION_RECORDED,
    ]
    assert {event.claim_id for event in events.events} == {claim.claim_id}
    assert all(event.payload["rule_id"] for event in events.events)
    assert all(event.payload["evidence"] for event in events.events)
    assert "denial prevented" not in str(recorded).lower()
    assert "intervention_recorded" in events.events[-1].model_dump_json()


def test_typed_readiness_event_rejects_missing_evidence() -> None:
    with pytest.raises(ValidationError):
        AgentEvent(
            session_id="session-1",
            agent="claim_readiness",
            event_type=EventType.DENIAL_RISK_DETECTED,
            member_id="MBR00001",
            claim_id="CLM000001",
            payload={"rule_id": "RULE-1"},
        )
