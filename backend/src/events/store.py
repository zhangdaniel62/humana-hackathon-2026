"""Durable append-only adapter for structured operational events."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Protocol

from ..models import AgentEvent

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "operations" / "schema.sql"


class EventStore(Protocol):
    def append(self, event: AgentEvent) -> bool: ...

    def load(self) -> list[AgentEvent]: ...


class SQLiteEventStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))

    def append(self, event: AgentEvent) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO agent_events ("
                "event_id, timestamp, session_id, agent, event_type, member_id, "
                "claim_id, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(event.event_id),
                    event.timestamp.isoformat(),
                    event.session_id,
                    event.agent,
                    event.event_type.value,
                    event.member_id,
                    event.claim_id,
                    json.dumps(event.payload, sort_keys=True),
                ),
            )
        return cursor.rowcount == 1

    def load(self) -> list[AgentEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_events ORDER BY timestamp, event_id"
            ).fetchall()
        return [
            AgentEvent.model_validate(
                {
                    "event_id": row["event_id"],
                    "timestamp": row["timestamp"],
                    "session_id": row["session_id"],
                    "agent": row["agent"],
                    "event_type": row["event_type"],
                    "member_id": row["member_id"],
                    "claim_id": row["claim_id"],
                    "payload": json.loads(row["payload_json"]),
                }
            )
            for row in rows
        ]
