"""Transactional SQLite persistence for live support rooms and messages."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ..auth.models import AuthUser
from ..models.support import (
    SupportMessage,
    SupportParticipant,
    SupportRoom,
    SupportRoomStatus,
)

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class SupportRoomConflict(Exception):
    """The requested state transition is incompatible with the room state."""


def _datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


class SupportStore:
    """Synchronous store with short transactions and one connection per call."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))

    def create_or_get_room(
        self, customer: AuthUser, *, source_session_id: str | None = None
    ) -> SupportRoom:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._open_room_row(connection, customer.id)
            if row is None:
                room_id = str(uuid4())
                connection.execute(
                    "INSERT INTO support_rooms "
                    "(id, customer_id, source_session_id, status) "
                    "VALUES (?, ?, ?, 'waiting')",
                    (room_id, customer.id, source_session_id),
                )
                row = self._room_row(connection, room_id)
            assert row is not None
            return self._to_room(row)

    def get_current_room(self, customer_id: int) -> SupportRoom | None:
        with self._connect() as connection:
            row = self._open_room_row(connection, customer_id)
        return self._to_room(row) if row is not None else None

    def get_room(self, room_id: str) -> SupportRoom | None:
        with self._connect() as connection:
            row = self._room_row(connection, room_id)
        return self._to_room(row) if row is not None else None

    def list_waiting_rooms(self) -> list[SupportRoom]:
        with self._connect() as connection:
            rows = connection.execute(
                self._ROOM_SELECT
                + " WHERE rooms.status = 'waiting' ORDER BY rooms.created_at, rooms.id"
            ).fetchall()
        return [self._to_room(row) for row in rows]

    def claim_room(self, room_id: str, representative: AuthUser) -> SupportRoom:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE support_rooms SET status = 'active', assigned_rep_id = ?, "
                "claimed_at = unixepoch() WHERE id = ? AND status = 'waiting' "
                "AND assigned_rep_id IS NULL",
                (representative.id, room_id),
            )
            row = self._room_row(connection, room_id)
            if row is None:
                raise KeyError(room_id)
            if cursor.rowcount != 1:
                if (
                    row["status"] == SupportRoomStatus.ACTIVE.value
                    and row["assigned_rep_id"] == representative.id
                ):
                    return self._to_room(row)
                raise SupportRoomConflict("Room is no longer available")
            return self._to_room(row)

    def complete_room(self, room_id: str, representative: AuthUser) -> SupportRoom:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE support_rooms SET status = 'completed', "
                "completed_at = unixepoch() WHERE id = ? AND status = 'active' "
                "AND assigned_rep_id = ?",
                (room_id, representative.id),
            )
            row = self._room_row(connection, room_id)
            if row is None:
                raise KeyError(room_id)
            if cursor.rowcount != 1:
                raise SupportRoomConflict(
                    "Only the assigned representative can complete an active room"
                )
            return self._to_room(row)

    def list_messages(self, room_id: str) -> list[SupportMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                self._MESSAGE_SELECT
                + " WHERE messages.room_id = ? ORDER BY messages.id",
                (room_id,),
            ).fetchall()
        return [self._to_message(row) for row in rows]

    def append_message(
        self,
        room_id: str,
        sender: AuthUser,
        *,
        client_message_id: str,
        text: str,
    ) -> tuple[SupportMessage, bool]:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO support_messages "
                "(room_id, sender_user_id, client_message_id, text) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (room_id, sender.id, client_message_id, text),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                self._MESSAGE_SELECT
                + " WHERE messages.room_id = ? AND messages.sender_user_id = ? "
                "AND messages.client_message_id = ?",
                (room_id, sender.id, client_message_id),
            ).fetchone()
        assert row is not None
        return self._to_message(row), created

    _ROOM_SELECT = """
        SELECT rooms.id, rooms.status, rooms.source_session_id, rooms.created_at,
               rooms.claimed_at, rooms.completed_at, rooms.assigned_rep_id,
               customer.id AS customer_id, customer.username AS customer_username,
               customer.role AS customer_role,
               representative.username AS rep_username,
               representative.role AS rep_role
        FROM support_rooms AS rooms
        JOIN users AS customer ON customer.id = rooms.customer_id
        LEFT JOIN users AS representative ON representative.id = rooms.assigned_rep_id
    """

    _MESSAGE_SELECT = """
        SELECT messages.id, messages.room_id, messages.client_message_id,
               messages.text, messages.created_at, sender.id AS sender_id,
               sender.username AS sender_username, sender.role AS sender_role
        FROM support_messages AS messages
        JOIN users AS sender ON sender.id = messages.sender_user_id
    """

    @classmethod
    def _room_row(
        cls, connection: sqlite3.Connection, room_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            cls._ROOM_SELECT + " WHERE rooms.id = ?", (room_id,)
        ).fetchone()

    @classmethod
    def _open_room_row(
        cls, connection: sqlite3.Connection, customer_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            cls._ROOM_SELECT
            + " WHERE rooms.customer_id = ? "
            "AND rooms.status IN ('waiting', 'active') "
            "ORDER BY rooms.created_at DESC LIMIT 1",
            (customer_id,),
        ).fetchone()

    @staticmethod
    def _to_room(row: sqlite3.Row) -> SupportRoom:
        assigned_rep = None
        if row["assigned_rep_id"] is not None:
            assigned_rep = SupportParticipant(
                id=row["assigned_rep_id"],
                username=row["rep_username"],
                role=row["rep_role"],
            )
        return SupportRoom(
            id=row["id"],
            status=row["status"],
            customer=SupportParticipant(
                id=row["customer_id"],
                username=row["customer_username"],
                role=row["customer_role"],
            ),
            assigned_rep=assigned_rep,
            source_session_id=row["source_session_id"],
            created_at=_datetime(row["created_at"]),
            claimed_at=_datetime(row["claimed_at"]),
            completed_at=_datetime(row["completed_at"]),
        )

    @staticmethod
    def _to_message(row: sqlite3.Row) -> SupportMessage:
        return SupportMessage(
            id=row["id"],
            room_id=row["room_id"],
            client_message_id=row["client_message_id"],
            text=row["text"],
            sender=SupportParticipant(
                id=row["sender_id"],
                username=row["sender_username"],
                role=row["sender_role"],
            ),
            created_at=_datetime(row["created_at"]),
        )
