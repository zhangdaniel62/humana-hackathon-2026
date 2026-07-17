"""Process-local registry for live support WebSocket connections only."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from ..auth.models import AuthUser, UserRole


@dataclass(eq=False, slots=True)
class SupportConnection:
    websocket: WebSocket
    user: AuthUser
    voice_enabled: bool = False
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send_json(self, payload: dict) -> None:
        async with self.send_lock:
            await self.websocket.send_json(payload)

    async def send_bytes(self, payload: bytes) -> None:
        async with self.send_lock:
            await self.websocket.send_bytes(payload)


class SupportRegistry:
    """Coordinate currently connected sockets without storing durable state."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._rooms: dict[str, set[SupportConnection]] = {}

    async def join(
        self, room_id: str, websocket: WebSocket, user: AuthUser
    ) -> SupportConnection:
        connection = SupportConnection(websocket=websocket, user=user)
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(connection)
        return connection

    async def leave(self, room_id: str, connection: SupportConnection) -> None:
        async with self._lock:
            connections = self._rooms.get(room_id)
            if connections is None:
                return
            connections.discard(connection)
            if not connections:
                self._rooms.pop(room_id, None)

    async def set_voice(
        self, room_id: str, connection: SupportConnection, enabled: bool
    ) -> None:
        async with self._lock:
            if connection in self._rooms.get(room_id, set()):
                connection.voice_enabled = enabled

    async def live_state(self, room_id: str) -> tuple[dict, dict]:
        async with self._lock:
            connections = tuple(self._rooms.get(room_id, ()))
        customer_connections = [
            item for item in connections if item.user.role is UserRole.CUSTOMER
        ]
        rep_connections = [
            item for item in connections if item.user.role is UserRole.REP
        ]
        presence = {
            "customer": bool(customer_connections),
            "rep": bool(rep_connections),
        }
        voice = {
            "customer_enabled": any(
                item.voice_enabled for item in customer_connections
            ),
            "rep_enabled": any(item.voice_enabled for item in rep_connections),
        }
        return presence, voice

    async def broadcast_json(self, room_id: str, payload: dict) -> None:
        async with self._lock:
            recipients = tuple(self._rooms.get(room_id, ()))
        await asyncio.gather(
            *(self._send_json_safely(item, payload) for item in recipients)
        )

    async def broadcast_presence(self, room_id: str) -> None:
        presence, voice = await self.live_state(room_id)
        await self.broadcast_json(
            room_id,
            {"type": "presence", "presence": presence, "voice": voice},
        )

    async def relay_audio(
        self, room_id: str, sender: SupportConnection, payload: bytes
    ) -> bool:
        async with self._lock:
            connections = tuple(self._rooms.get(room_id, ()))
            if sender not in connections or not sender.voice_enabled:
                return False
            recipients = tuple(
                item
                for item in connections
                if item.user.role is not sender.user.role and item.voice_enabled
            )
        if not recipients:
            return False
        results = await asyncio.gather(
            *(self._send_bytes_safely(item, payload) for item in recipients)
        )
        return any(results)

    @staticmethod
    async def _send_json_safely(
        connection: SupportConnection, payload: dict
    ) -> bool:
        try:
            await connection.send_json(payload)
            return True
        except Exception:
            return False

    @staticmethod
    async def _send_bytes_safely(
        connection: SupportConnection, payload: bytes
    ) -> bool:
        try:
            await connection.send_bytes(payload)
            return True
        except Exception:
            return False
