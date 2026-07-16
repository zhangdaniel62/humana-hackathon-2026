"""WebSocket bridge between a browser microphone and the ADK live runner.

Wire protocol with the browser:
- upstream binary frames: raw 16-bit PCM mono microphone audio at 16 kHz
- upstream text frames: JSON ``{"type": "text", "text": "..."}`` typed input
- downstream binary frames: raw 16-bit PCM mono agent audio at 24 kHz
- downstream text frames: JSON with ``type`` of ``user_transcript``,
  ``agent_transcript``, ``interrupted``, or ``turn_complete``
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types

from ..agents.orchestrator import create_voice_orchestrator
from ..settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

VOICE_APP_NAME = "claim_assist_voice"
VOICE_USER_ID = "demo-caller"
INPUT_AUDIO_MIME_TYPE = "audio/pcm;rate=16000"

_runner: InMemoryRunner | None = None


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
    """Run one live voice session over a browser WebSocket."""

    await websocket.accept()
    runner = _get_runner()
    session = await runner.session_service.create_session(
        app_name=VOICE_APP_NAME,
        user_id=VOICE_USER_ID,
    )
    live_queue = LiveRequestQueue()
    try:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(_pump_caller_audio(websocket, live_queue))
            tasks.create_task(
                _pump_agent_events(websocket, runner, session.id, live_queue)
            )
    except* WebSocketDisconnect:
        pass
    except* Exception:
        logger.exception("Voice session %s failed", session.id)
    finally:
        live_queue.close()


async def _pump_caller_audio(
    websocket: WebSocket, live_queue: LiveRequestQueue
) -> None:
    """Forward microphone audio (and typed fallback text) into the live queue."""

    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(code=message.get("code") or 1000)
        if audio := message.get("bytes"):
            live_queue.send_realtime(
                types.Blob(data=audio, mime_type=INPUT_AUDIO_MIME_TYPE)
            )
        elif text := message.get("text"):
            payload = json.loads(text)
            if payload.get("type") == "text" and payload.get("text"):
                live_queue.send_content(
                    types.Content(
                        role="user", parts=[types.Part(text=payload["text"])]
                    )
                )


async def _pump_agent_events(
    websocket: WebSocket,
    runner: InMemoryRunner,
    session_id: str,
    live_queue: LiveRequestQueue,
) -> None:
    """Stream agent audio, transcripts, and turn signals back to the browser."""

    async for event in runner.run_live(
        user_id=VOICE_USER_ID,
        session_id=session_id,
        live_request_queue=live_queue,
        run_config=_build_run_config(),
    ):
        content = event.content
        for part in (content.parts if content and content.parts else []):
            if part.inline_data and part.inline_data.data:
                await websocket.send_bytes(part.inline_data.data)
        if event.input_transcription and event.input_transcription.text:
            await _send_json(
                websocket,
                {"type": "user_transcript", "text": event.input_transcription.text},
            )
        if event.output_transcription and event.output_transcription.text:
            await _send_json(
                websocket,
                {"type": "agent_transcript", "text": event.output_transcription.text},
            )
        if event.interrupted:
            await _send_json(websocket, {"type": "interrupted"})
        if event.turn_complete:
            await _send_json(websocket, {"type": "turn_complete"})
    await websocket.close()


async def _send_json(websocket: WebSocket, payload: dict) -> None:
    await websocket.send_text(json.dumps(payload))
