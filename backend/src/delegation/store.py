"""Trace stores that intentionally reject prompts, utterances, and results."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ..models import DelegationTrace

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "operations" / "schema.sql"


class TraceSink(Protocol):
    def record(self, trace: DelegationTrace) -> None: ...


class InMemoryDelegationTraceStore:
    def __init__(self) -> None:
        self.traces: list[DelegationTrace] = []

    def record(self, trace: DelegationTrace) -> None:
        self.traces.append(trace)

    def list(self, *, limit: int = 100) -> list[DelegationTrace]:
        return list(reversed(self.traces[-limit:]))


class DelegationTraceStore:
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

    def record(self, trace: DelegationTrace) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO delegation_traces ("
                "trace_id, session_id, work_item_id, specialist, started_at, "
                "completed_at, latency_ms, outcome, error_code"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trace.trace_id,
                    trace.session_id,
                    trace.work_item_id,
                    trace.specialist,
                    int(trace.started_at.timestamp()),
                    int(trace.completed_at.timestamp()),
                    trace.latency_ms,
                    trace.outcome,
                    trace.error_code,
                ),
            )

    def list(self, *, limit: int = 100) -> list[DelegationTrace]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM delegation_traces "
                "ORDER BY started_at DESC, trace_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            DelegationTrace(
                trace_id=row["trace_id"],
                session_id=row["session_id"],
                work_item_id=row["work_item_id"],
                specialist=row["specialist"],
                started_at=datetime.fromtimestamp(row["started_at"], UTC),
                completed_at=datetime.fromtimestamp(row["completed_at"], UTC),
                latency_ms=row["latency_ms"],
                outcome=row["outcome"],
                error_code=row["error_code"],
            )
            for row in rows
        ]
