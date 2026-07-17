"""Transport-level tests for the browser live-voice WebSocket."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import WebSocketDisconnect

from src.api.voice import (
    ConversationModeState,
    _pump_agent_events,
    _pump_caller_audio,
    _run_conversation,
)
from src.auth.models import AuthUser, Capability, UserRole
from src.events import event_log
from src.models import EventType
from src.services.session_summary import session_summary_store

REP_USER = AuthUser(
    id=3,
    username="rep",
    role=UserRole.REP,
    capabilities=(Capability.REP_QUEUE, Capability.CHAT, Capability.VOICE),
)


@pytest.fixture(autouse=True)
def reset_voice_projections():
    event_log.clear()
    session_summary_store.clear()
    yield
    event_log.clear()
    session_summary_store.clear()


class StubWebSocket:
    def __init__(self, incoming: list[dict] | None = None) -> None:
        self.incoming = list(incoming or [])
        self.accepted = False
        self.sent_json: list[dict] = []
        self.sent_bytes: list[bytes] = []
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def receive(self) -> dict:
        if self.incoming:
            return self.incoming.pop(0)
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send_json(self, payload: dict) -> None:
        self.sent_json.append(payload)

    async def send_bytes(self, payload: bytes) -> None:
        self.sent_bytes.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.close_code = code


class StubLiveQueue:
    def __init__(self) -> None:
        self.audio = []
        self.content = []

    def send_realtime(self, blob) -> None:
        self.audio.append(blob)

    def send_content(self, content) -> None:
        self.content.append(content)


class StubSessionService:
    def __init__(self) -> None:
        self.last_kwargs = None

    async def create_session(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(id=kwargs["session_id"], state=kwargs["state"])


class WaitingRunner:
    def __init__(self) -> None:
        self.session_service = StubSessionService()
        self.run_kwargs = None

    async def run_live(self, **kwargs):
        self.run_kwargs = kwargs
        await asyncio.Event().wait()
        if False:
            yield None


class EventRunner:
    async def run_live(self, **kwargs):
        yield SimpleNamespace(
            content=SimpleNamespace(
                parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b"audio"))]
            ),
            input_transcription=SimpleNamespace(text="hello"),
            output_transcription=SimpleNamespace(text="hi there"),
            interrupted=True,
            turn_complete=True,
        )


def test_voice_connection_announces_session_and_records_lifecycle() -> None:
    websocket = StubWebSocket(
        [{"type": "websocket.disconnect", "code": 1000}]
    )

    runner = WaitingRunner()
    with patch("src.api.voice._get_runner", return_value=runner):
        asyncio.run(_run_conversation(websocket, REP_USER, allow_voice=True))

    assert websocket.accepted is True
    started = websocket.sent_json[0]
    assert started["type"] == "session_started"
    assert started["mode"] == "chat"
    assert started["summary_url"] == (
        f"/api/sessions/{started['session_id']}/summary"
    )
    assert started["input_audio"]["sample_rate_hz"] == 16_000
    assert started["output_audio"]["sample_rate_hz"] == 24_000
    assert session_summary_store.get(started["session_id"]).status == "incomplete"
    assert [event.event_type for event in event_log.events] == [
        EventType.SESSION_STARTED,
        EventType.SESSION_COMPLETED,
    ]
    assert event_log.events[0].payload["initial_mode"] == "chat"
    assert event_log.events[1].payload["final_mode"] == "chat"
    assert session_summary_store.owner_user_id(started["session_id"]) == "3"
    assert runner.session_service.last_kwargs["user_id"] == "3"
    assert runner.session_service.last_kwargs["state"]["auth_role"] == "rep"
    assert runner.run_kwargs["user_id"] == "3"


def test_invalid_typed_message_is_rejected_without_ending_call() -> None:
    websocket = StubWebSocket(
        [
            {"type": "websocket.receive", "text": "not-json"},
            {
                "type": "websocket.receive",
                "text": '{"type":"text","text":"  check my claim  "}',
            },
            {"type": "websocket.disconnect", "code": 1000},
        ]
    )
    queue = StubLiveQueue()

    with pytest.raises(WebSocketDisconnect):
        asyncio.run(
            _pump_caller_audio(
                websocket,
                queue,
                ConversationModeState(),
            )
        )

    assert websocket.sent_json == [
        {
            "type": "error",
            "code": "invalid_message",
            "message": (
                "Send a supported JSON message with type 'text' or "
                "'set_mode'."
            ),
            "retryable": False,
        }
    ]
    assert queue.content[0].parts[0].text == "check my claim"


def test_voice_is_opt_in_and_can_switch_back_to_chat() -> None:
    websocket = StubWebSocket(
        [
            {"type": "websocket.receive", "bytes": b"ignored"},
            {
                "type": "websocket.receive",
                "text": '{"type":"set_mode","mode":"voice"}',
            },
            {"type": "websocket.receive", "bytes": b"microphone"},
            {
                "type": "websocket.receive",
                "text": '{"type":"set_mode","mode":"chat"}',
            },
            {"type": "websocket.receive", "bytes": b"ignored-again"},
            {"type": "websocket.disconnect", "code": 1000},
        ]
    )
    queue = StubLiveQueue()
    mode_state = ConversationModeState()

    with pytest.raises(WebSocketDisconnect):
        asyncio.run(_pump_caller_audio(websocket, queue, mode_state))

    assert [message["type"] for message in websocket.sent_json] == [
        "error",
        "mode_changed",
        "mode_changed",
        "error",
    ]
    assert websocket.sent_json[0]["code"] == "voice_mode_required"
    assert websocket.sent_json[1]["mode"] == "voice"
    assert websocket.sent_json[2]["mode"] == "chat"
    assert [blob.data for blob in queue.audio] == [b"microphone"]
    assert mode_state.mode == "chat"


def test_agent_events_include_summary_correlation() -> None:
    websocket = StubWebSocket()

    asyncio.run(
        _pump_agent_events(
            websocket,
            EventRunner(),
            "session-123",
            StubLiveQueue(),
            ConversationModeState(mode="voice"),
            "3",
        )
    )

    assert websocket.sent_bytes == [b"audio"]
    assert [message["type"] for message in websocket.sent_json] == [
        "user_transcript",
        "agent_transcript",
        "interrupted",
        "turn_complete",
    ]
    assert websocket.sent_json[-1] == {
        "type": "turn_complete",
        "session_id": "session-123",
        "summary_url": "/api/sessions/session-123/summary",
    }
    assert websocket.close_code == 1000


def test_chat_mode_suppresses_spoken_audio_but_keeps_transcripts() -> None:
    websocket = StubWebSocket()

    asyncio.run(
        _pump_agent_events(
            websocket,
            EventRunner(),
            "session-123",
            StubLiveQueue(),
            ConversationModeState(),
            "3",
        )
    )

    assert websocket.sent_bytes == []
    assert [message["type"] for message in websocket.sent_json] == [
        "user_transcript",
        "agent_transcript",
        "interrupted",
        "turn_complete",
    ]


def test_session_initialization_failure_is_user_safe() -> None:
    websocket = StubWebSocket()

    with patch(
        "src.api.voice._get_runner", side_effect=RuntimeError("secret detail")
    ):
        asyncio.run(_run_conversation(websocket, REP_USER, allow_voice=True))

    assert websocket.sent_json == [
        {
            "type": "error",
            "code": "session_initialization_failed",
            "message": (
                "The conversation could not be started. Please try again "
                "shortly."
            ),
            "retryable": True,
        }
    ]
    assert "secret detail" not in str(websocket.sent_json)
    assert websocket.close_code == 1011
