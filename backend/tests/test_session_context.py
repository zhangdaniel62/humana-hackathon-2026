"""Shared session and ROI-gate behavior."""

from __future__ import annotations

from src.agents.session_context import build_establish_member_context_tool
from src.clients.member_records import Authorization, FakeMemberRecordsClient
from src.events import EventLog
from src.models import EventType


class StubContext:
    def __init__(self, **state) -> None:
        self.state = state


def client() -> FakeMemberRecordsClient:
    return FakeMemberRecordsClient(
        [
            Authorization(
                "AUTH1",
                "MBR00001",
                "Daniel Barrett",
                "Sibling",
                True,
                "2099-12-31",
                False,
            ),
            Authorization(
                "AUTH2",
                "MBR00002",
                "Expired Caller",
                "Parent",
                True,
                "2020-01-01",
                True,
            ),
        ]
    )


def test_context_records_verified_roi_and_session_start() -> None:
    events = EventLog()
    tool = build_establish_member_context_tool(client(), events)
    context = StubContext()

    payload = tool.func("Daniel Barrett", "mbr00001", context)

    assert payload["roi"]["status"] == "verified"
    assert context.state["subject_member_id"] == "MBR00001"
    assert context.state["roi_status"] == "verified"
    assert context.state["agent_findings"]["roi_gatekeeper"]["status"] == "verified"
    assert [event.event_type for event in events.events] == [
        EventType.SESSION_STARTED
    ]


def test_context_distinguishes_expired_and_unknown_and_emits_gap() -> None:
    for member_id, caller_name, expected in (
        ("MBR00002", "Expired Caller", "expired"),
        ("MBR99999", "Unknown Caller", "unknown"),
    ):
        events = EventLog()
        tool = build_establish_member_context_tool(client(), events)
        context = StubContext()

        payload = tool.func(caller_name, member_id, context)

        assert payload["roi"]["status"] == expected
        assert [event.event_type for event in events.events] == [
            EventType.SESSION_STARTED,
            EventType.ROI_GAP_DETECTED,
        ]


def test_authenticated_self_requires_no_roi() -> None:
    tool = build_establish_member_context_tool(client(), EventLog())
    context = StubContext(caller_id="MBR00001")

    payload = tool.func("The Member", "MBR00001", context)

    assert payload["roi"]["status"] == "not_required"


def test_session_started_is_emitted_once_even_with_preseeded_session_id() -> None:
    events = EventLog()
    tool = build_establish_member_context_tool(client(), events)
    context = StubContext(session_id="SESSION-1")

    tool.func("Daniel Barrett", "MBR00001", context)
    tool.func("Daniel Barrett", "MBR00001", context)

    assert [event.event_type for event in events.events] == [
        EventType.SESSION_STARTED
    ]
