"""Authenticated customer-to-representative support room HTTP and WS API."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, status
from fastapi.websockets import WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from ..auth.dependencies import CurrentUser, require_role
from ..auth.models import AuthUser, UserRole
from ..models.support import (
    CreateSupportRoomRequest,
    SupportRoom,
    SupportRoomStatus,
    SupportTextInput,
    SupportVoiceInput,
)
from ..services.session_summary import session_summary_store
from ..support import SupportConnection, SupportRoomConflict

logger = logging.getLogger(__name__)
router = APIRouter(tags=["support"])

MAX_AUDIO_FRAME_BYTES = 64 * 1024
_CLIENT_MESSAGE = TypeAdapter(SupportTextInput | SupportVoiceInput)
_Customer = Annotated[AuthUser, Depends(require_role(UserRole.CUSTOMER))]
_Representative = Annotated[AuthUser, Depends(require_role(UserRole.REP))]


@router.post("/api/support/rooms", response_model=SupportRoom)
def create_support_room(
    request: Request,
    customer: _Customer,
    payload: CreateSupportRoomRequest | None = None,
) -> SupportRoom:
    source_session_id = payload.source_session_id if payload is not None else None
    if source_session_id is not None and (
        session_summary_store.owner_user_id(source_session_id)
        != str(customer.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source session does not belong to the authenticated customer",
        )
    return request.app.state.support_store.create_or_get_room(
        customer, source_session_id=source_session_id
    )


@router.get("/api/support/rooms/current", response_model=SupportRoom | None)
def current_support_room(request: Request, customer: _Customer) -> SupportRoom | None:
    return request.app.state.support_store.get_current_room(customer.id)


@router.get("/api/support/queue", response_model=list[SupportRoom])
def support_queue(
    request: Request, representative: _Representative
) -> list[SupportRoom]:
    return request.app.state.support_store.list_waiting_rooms()


@router.post("/api/support/rooms/{room_id}/claim", response_model=SupportRoom)
def claim_support_room(
    room_id: str, request: Request, representative: _Representative
) -> SupportRoom:
    try:
        return request.app.state.support_store.claim_room(room_id, representative)
    except KeyError:
        raise HTTPException(status_code=404, detail="Support room not found") from None
    except SupportRoomConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/api/support/rooms/{room_id}/complete", response_model=SupportRoom)
def complete_support_room(
    room_id: str, request: Request, representative: _Representative
) -> SupportRoom:
    try:
        return request.app.state.support_store.complete_room(room_id, representative)
    except KeyError:
        raise HTTPException(status_code=404, detail="Support room not found") from None
    except SupportRoomConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.websocket("/ws/support/{room_id}")
async def support_websocket(websocket: WebSocket, room_id: str) -> None:
    user = await _authenticate_websocket(websocket)
    if user is None:
        return
    store = websocket.app.state.support_store
    room = store.get_room(room_id)
    if room is None:
        await _close_safely(websocket, 4404)
        return
    if not _may_join(room, user):
        await _close_safely(websocket, 4403)
        return

    await websocket.accept()
    registry = websocket.app.state.support_registry
    connection = await registry.join(room_id, websocket, user)
    try:
        presence, voice = await registry.live_state(room_id)
        await connection.send_json(
            {
                "type": "snapshot",
                "room": room.model_dump(mode="json"),
                "messages": [
                    item.model_dump(mode="json")
                    for item in store.list_messages(room_id)
                ],
                "presence": presence,
                "voice": voice,
            }
        )
        await registry.broadcast_presence(room_id)
        await _receive_support_messages(room_id, connection, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        await registry.leave(room_id, connection)
        await registry.broadcast_presence(room_id)


async def _receive_support_messages(
    room_id: str, connection: SupportConnection, websocket: WebSocket
) -> None:
    store = websocket.app.state.support_store
    registry = websocket.app.state.support_registry
    while True:
        incoming = await websocket.receive()
        if incoming["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(incoming.get("code", 1000))
        binary = incoming.get("bytes")
        if binary is not None:
            if len(binary) > MAX_AUDIO_FRAME_BYTES:
                await _send_error(
                    connection,
                    "audio_frame_too_large",
                    "Audio frames must not exceed 65536 bytes",
                )
                continue
            room = store.get_room(room_id)
            if room is None or room.status is not SupportRoomStatus.ACTIVE:
                await _send_error(
                    connection,
                    "voice_unavailable",
                    "Voice relay is available only in an active support room",
                )
                continue
            if not await registry.relay_audio(room_id, connection, binary):
                await _send_error(
                    connection,
                    "voice_unavailable",
                    "Both participants must be present with voice enabled",
                )
            continue

        text = incoming.get("text")
        try:
            parsed = _CLIENT_MESSAGE.validate_python(json.loads(text or ""))
        except (json.JSONDecodeError, ValidationError):
            await _send_error(
                connection,
                "invalid_message",
                "Send a supported 'text' or 'set_voice' JSON message",
            )
            continue

        room = store.get_room(room_id)
        if room is None or room.status is SupportRoomStatus.COMPLETED:
            await _send_error(
                connection, "room_completed", "This support room is completed"
            )
            continue
        if room.status is not SupportRoomStatus.ACTIVE:
            await _send_error(
                connection,
                "room_not_active",
                "Wait for a representative to claim this support room",
            )
            continue
        if isinstance(parsed, SupportVoiceInput):
            await registry.set_voice(room_id, connection, parsed.enabled)
            await registry.broadcast_presence(room_id)
            continue

        message, created = store.append_message(
            room_id,
            connection.user,
            client_message_id=parsed.client_message_id,
            text=parsed.text,
        )
        envelope = {
            "type": "text",
            "message": message.model_dump(mode="json"),
        }
        if created:
            await registry.broadcast_json(room_id, envelope)
        else:
            await connection.send_json(envelope)


def _may_join(room: SupportRoom, user: AuthUser) -> bool:
    if user.role is UserRole.CUSTOMER:
        return room.customer.id == user.id
    if user.role is UserRole.REP:
        return room.assigned_rep is not None and room.assigned_rep.id == user.id
    return False


async def _authenticate_websocket(websocket: WebSocket) -> AuthUser | None:
    settings = websocket.app.state.auth_settings
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        logger.info("Denied support WebSocket from untrusted origin=%s", origin)
        await _close_safely(websocket, 4403)
        return None
    token = websocket.cookies.get(settings.cookie_name)
    user = settings.bypass_user() or websocket.app.state.auth_store.resolve_session(
        token
    )
    if user is None:
        await _close_safely(websocket, 4401)
        return None
    if user.role not in {UserRole.CUSTOMER, UserRole.REP}:
        await _close_safely(websocket, 4403)
        return None
    return user


async def _send_error(
    connection: SupportConnection, code: str, message: str
) -> None:
    await connection.send_json({"type": "error", "code": code, "message": message})


async def _close_safely(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except RuntimeError:
        pass
