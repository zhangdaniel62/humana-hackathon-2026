"""Chat-first WebSocket bridge to the ADK live conversation runner.

Wire protocol with the browser:
- upstream binary frames: raw 16-bit PCM mono microphone audio at 16 kHz
- upstream text frames: JSON ``{"type": "text", "text": "..."}`` typed input
- upstream mode frames: JSON ``{"type": "set_mode", "mode": "chat|voice"}``
- downstream binary frames: raw 16-bit PCM mono agent audio at 24 kHz
- downstream text frames: validated JSON messages for session correlation,
  transcripts, interruption, turn completion, and user-safe errors
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import ValidationError

from ..agents.orchestrator import create_voice_orchestrator
from ..auth.models import AuthUser, UserRole
from ..events import event_log
from ..models import (
    AgentEvent,
    EventType,
    VoiceError,
    VoiceInterrupted,
    VoiceModeChanged,
    VoiceServerMessage,
    VoiceSessionStarted,
    VoiceSetModeInput,
    VoiceTextInput,
    VoiceTranscript,
    VoiceTurnComplete,
    voice_client_message_adapter,
)
from ..services.session_summary import session_summary_store
from ..settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

VOICE_APP_NAME = "claim_assist_voice"
INPUT_AUDIO_MIME_TYPE = "audio/pcm;rate=16000"
SESSION_SUMMARY_PATH = "/api/sessions/{session_id}/summary"

_runner: InMemoryRunner | None = None


@dataclass(slots=True)
class ConversationModeState:
    """Mutable per-connection presentation mode shared by both socket pumps."""

    mode: str = "chat"
    audio_warning_sent: bool = False
    voice_allowed: bool = True


def _get_runner() -> InMemoryRunner:
    """Create the shared live runner on first use.

    Deferred because building the orchestrator opens a BigQuery client,
    which needs Google credentials that are absent at import time in tests.
    """

    global _runner
    if _runner is None:
        _runner = InMemoryRunner(
            agent=create_voice_orchestrator(),
            app_name=VOICE_APP_NAME,
        )
    return _runner


def _build_run_config() -> RunConfig:
    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=settings.live_voice_name
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


@router.websocket("/ws/voice")
async def voice_call(websocket: WebSocket) -> None:
    """Run the rep-only backward-compatible voice endpoint."""

    user = await _authenticate_websocket(websocket, allowed_roles={UserRole.REP})
    if user is not None:
        await _run_conversation(websocket, user, allow_voice=True)


@router.websocket("/ws/conversation")
async def conversation(websocket: WebSocket) -> None:
    """Run authenticated customer chat or a rep chat/voice conversation."""

    user = await _authenticate_websocket(
        websocket, allowed_roles={UserRole.CUSTOMER, UserRole.REP}
    )
    if user is not None:
        await _run_conversation(
            websocket,
            user,
            allow_voice=user.role is UserRole.REP,
        )


async def _authenticate_websocket(
    websocket: WebSocket, *, allowed_roles: set[UserRole]
) -> AuthUser | None:
    settings = websocket.app.state.auth_settings
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        logger.info("Denied WebSocket from untrusted origin=%s", origin)
        await _close_safely(websocket, code=4403)
        return None

    token = websocket.cookies.get(settings.cookie_name)
    user = websocket.app.state.auth_store.resolve_session(token)
    if user is None:
        logger.info("Denied unauthenticated WebSocket path=%s", websocket.url.path)
        await _close_safely(websocket, code=4401)
        return None
    if user.role not in allowed_roles:
        logger.info(
            "Denied WebSocket user=%s role=%s path=%s",
            user.username,
            user.role.value,
            websocket.url.path,
        )
        await _close_safely(websocket, code=4403)
        return None
    return user


async def _run_conversation(
    websocket: WebSocket, user: AuthUser, *, allow_voice: bool
) -> None:
    """Run one authenticated conversation with role-appropriate modes."""

    await websocket.accept()
    try:
        runner = _get_runner()
        session_id = str(uuid4())
        initial_state = {
            "session_id": session_id,
            "channel": "conversation",
            "conversation_mode": "chat",
            "auth_user_id": str(user.id),
            "auth_role": user.role.value,
            # The transport emits SESSION_STARTED as soon as the call connects.
            # The context tool uses this flag to avoid publishing a duplicate.
            "_session_started_emitted": True,
        }
        session = await runner.session_service.create_session(
            app_name=VOICE_APP_NAME,
            user_id=str(user.id),
            session_id=session_id,
            state=initial_state,
        )
    except Exception:
        logger.exception("Could not initialize a live conversation session")
        await _send_error_safely(
            websocket,
            VoiceError(
                code="session_initialization_failed",
                message=(
                    "The conversation could not be started. Please try again "
                    "shortly."
                ),
                retryable=True,
            ),
        )
        await _close_safely(websocket, code=1011)
        return

    summary_url = SESSION_SUMMARY_PATH.format(session_id=session.id)
    session_summary_store.capture(initial_state)
    event_log.publish_nowait(
        AgentEvent(
            session_id=session.id,
            agent="orchestrator",
            event_type=EventType.SESSION_STARTED,
            payload={
                "channel": "conversation",
                "initial_mode": "chat",
                "synthetic": True,
            },
        )
    )
    started_at = monotonic()
    try:
        await _send_message(
            websocket,
            VoiceSessionStarted(
                session_id=session.id,
                summary_url=summary_url,
            ),
        )
    except (RuntimeError, WebSocketDisconnect):
        _publish_session_completed(
            session.id,
            started_at=started_at,
            transport_error=True,
        )
        return

    live_queue = LiveRequestQueue()
    mode_state = ConversationModeState(voice_allowed=allow_voice)
    live_failure: BaseException | None = None
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(
                _pump_caller_audio(websocket, live_queue, mode_state)
            )
            tasks.create_task(
                _pump_agent_events(
                    websocket,
                    runner,
                    session.id,
                    live_queue,
                    mode_state,
                    str(user.id),
                )
            )
    except* WebSocketDisconnect:
        pass
    except* Exception as exc_group:
        live_failure = exc_group
        logger.error("Voice session %s failed", session.id, exc_info=exc_group)
    finally:
        live_queue.close()
        _publish_session_completed(
            session.id,
            started_at=started_at,
            transport_error=live_failure is not None,
            final_mode=mode_state.mode,
        )

    if live_failure is not None:
        await _send_error_safely(
            websocket,
            VoiceError(
                code="live_model_unavailable",
                message=(
                    "The live conversation service is temporarily unavailable. "
                    "Your structured session results remain available; please retry."
                ),
                retryable=True,
            ),
        )
        await _close_safely(websocket, code=1011)


async def _pump_caller_audio(
    websocket: WebSocket,
    live_queue: LiveRequestQueue,
    mode_state: ConversationModeState,
) -> None:
    """Forward typed chat and explicitly enabled microphone audio."""

    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(code=message.get("code") or 1000)
        if audio := message.get("bytes"):
            if mode_state.mode != "voice":
                if not mode_state.audio_warning_sent:
                    code = (
                        "voice_mode_required"
                        if mode_state.voice_allowed
                        else "voice_forbidden"
                    )
                    message_text = (
                        "Choose voice mode before sending microphone audio."
                        if mode_state.voice_allowed
                        else "Voice mode is not available for this account."
                    )
                    await _send_message(
                        websocket,
                        VoiceError(
                            code=code,
                            message=message_text,
                        ),
                    )
                    mode_state.audio_warning_sent = True
                continue
            live_queue.send_realtime(
                types.Blob(data=audio, mime_type=INPUT_AUDIO_MIME_TYPE)
            )
        elif (text := message.get("text")) is not None:
            try:
                payload = voice_client_message_adapter.validate_json(text)
            except ValidationError:
                await _send_message(
                    websocket,
                    VoiceError(
                        code="invalid_message",
                        message=(
                            "Send a supported JSON message with type 'text' or "
                            "'set_mode'."
                        ),
                    ),
                )
                continue

            if isinstance(payload, VoiceTextInput):
                live_queue.send_content(
                    types.Content(
                        role="user", parts=[types.Part(text=payload.text)]
                    )
                )
            elif isinstance(payload, VoiceSetModeInput):
                if payload.mode == "voice" and not mode_state.voice_allowed:
                    await _send_message(
                        websocket,
                        VoiceError(
                            code="voice_forbidden",
                            message="Voice mode is not available for this account.",
                        ),
                    )
                    continue
                mode_state.mode = payload.mode
                mode_state.audio_warning_sent = False
                await _send_message(
                    websocket,
                    VoiceModeChanged(mode=payload.mode),
                )


async def _pump_agent_events(
    websocket: WebSocket,
    runner: InMemoryRunner,
    session_id: str,
    live_queue: LiveRequestQueue,
    mode_state: ConversationModeState,
    user_id: str,
) -> None:
    """Stream text in chat mode and add audio only after voice is selected."""

    async for event in runner.run_live(
        user_id=user_id,
        session_id=session_id,
        live_request_queue=live_queue,
        run_config=_build_run_config(),
    ):
        content = event.content
        for part in (content.parts if content and content.parts else []):
            if (
                mode_state.mode == "voice"
                and part.inline_data
                and part.inline_data.data
            ):
                await websocket.send_bytes(part.inline_data.data)
        if event.input_transcription and event.input_transcription.text:
            await _send_message(
                websocket,
                VoiceTranscript(
                    type="user_transcript", text=event.input_transcription.text
                ),
            )
        if event.output_transcription and event.output_transcription.text:
            await _send_message(
                websocket,
                VoiceTranscript(
                    type="agent_transcript", text=event.output_transcription.text
                ),
            )
        if event.interrupted:
            await _send_message(websocket, VoiceInterrupted())
        if event.turn_complete:
            await _send_message(
                websocket,
                VoiceTurnComplete(
                    session_id=session_id,
                    summary_url=SESSION_SUMMARY_PATH.format(session_id=session_id),
                ),
            )
    await _close_safely(websocket)


async def _send_message(
    websocket: WebSocket, payload: VoiceServerMessage
) -> None:
    await websocket.send_json(payload.model_dump(mode="json"))


async def _send_error_safely(websocket: WebSocket, payload: VoiceError) -> None:
    try:
        await _send_message(websocket, payload)
    except (RuntimeError, WebSocketDisconnect):
        pass


async def _close_safely(websocket: WebSocket, code: int = 1000) -> None:
    try:
        await websocket.close(code=code)
    except (RuntimeError, WebSocketDisconnect):
        pass


def _publish_session_completed(
    session_id: str,
    *,
    started_at: float,
    transport_error: bool,
    final_mode: str = "chat",
) -> None:
    event_log.publish_nowait(
        AgentEvent(
            session_id=session_id,
            agent="orchestrator",
            event_type=EventType.SESSION_COMPLETED,
            payload={
                "duration_seconds": round(monotonic() - started_at, 2),
                # The transport cannot truthfully infer resolution or repeat
                # contact from a closed socket, so those remain conservative.
                "resolved": False,
                "repeat_contact": False,
                "human_escalation": False,
                "channel": "conversation",
                "final_mode": final_mode,
                "transport_error": transport_error,
                "synthetic": True,
            },
        )
    )
