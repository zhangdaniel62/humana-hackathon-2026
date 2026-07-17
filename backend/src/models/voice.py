"""Validated messages for the browser-to-ADK live voice channel."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class VoiceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VoiceTextInput(VoiceMessage):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=4_000)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized


class VoiceSetModeInput(VoiceMessage):
    type: Literal["set_mode"] = "set_mode"
    mode: Literal["chat", "voice"]


VoiceClientMessage = Annotated[
    VoiceTextInput | VoiceSetModeInput,
    Field(discriminator="type"),
]
voice_client_message_adapter = TypeAdapter(VoiceClientMessage)


class VoiceAudioFormat(VoiceMessage):
    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate_hz: int
    channels: Literal[1] = 1


class VoiceSessionStarted(VoiceMessage):
    type: Literal["session_started"] = "session_started"
    session_id: str
    summary_url: str
    mode: Literal["chat"] = "chat"
    agent_audio_enabled: bool = True
    input_audio: VoiceAudioFormat = Field(
        default_factory=lambda: VoiceAudioFormat(sample_rate_hz=16_000)
    )
    output_audio: VoiceAudioFormat = Field(
        default_factory=lambda: VoiceAudioFormat(sample_rate_hz=24_000)
    )


class VoiceTranscript(VoiceMessage):
    type: Literal["user_transcript", "agent_transcript"]
    text: str


class VoiceInterrupted(VoiceMessage):
    type: Literal["interrupted"] = "interrupted"


class VoiceModeChanged(VoiceMessage):
    type: Literal["mode_changed"] = "mode_changed"
    mode: Literal["chat", "voice"]


class VoiceTurnComplete(VoiceMessage):
    type: Literal["turn_complete"] = "turn_complete"
    session_id: str
    summary_url: str


class VoiceError(VoiceMessage):
    type: Literal["error"] = "error"
    code: Literal[
        "invalid_message",
        "voice_forbidden",
        "voice_mode_required",
        "session_initialization_failed",
        "live_model_unavailable",
    ]
    message: str
    retryable: bool = False


VoiceServerMessage = (
    VoiceSessionStarted
    | VoiceTranscript
    | VoiceInterrupted
    | VoiceModeChanged
    | VoiceTurnComplete
    | VoiceError
)
