"""Typed contracts for authenticated customer-to-representative support rooms."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..auth.models import UserRole


class SupportRoomStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"


class SupportParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    username: str
    role: UserRole


class SupportRoom(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    status: SupportRoomStatus
    customer: SupportParticipant
    assigned_rep: SupportParticipant | None = None
    source_session_id: str | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


class SupportMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    room_id: str
    client_message_id: str
    text: str
    sender: SupportParticipant
    created_at: datetime


class CreateSupportRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_session_id: str | None = Field(default=None, max_length=128)

    @field_validator("source_session_id")
    @classmethod
    def normalize_source_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SupportTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    client_message_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=8_000)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "text":
            raise ValueError("type must be 'text'")
        return value

    @field_validator("client_message_id", "text")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class SupportVoiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    enabled: bool

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "set_voice":
            raise ValueError("type must be 'set_voice'")
        return value
