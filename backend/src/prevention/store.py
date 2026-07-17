"""SQLite persistence for idempotent scans and rep-owned work items."""

from __future__ import annotations

import sqlite3
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ..models import (
    QueueSnapshot,
    RepWorkItem,
    ScanResult,
    WorkItemCandidate,
    WorkItemStatus,
)

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "operations" / "schema.sql"


class PreventionConflictError(RuntimeError):
    """A queue item changed or cannot make the requested transition."""


class PreventionStore:
    """Database-enforced scan deduplication and work-item transitions."""

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

    def persist_scan(
        self,
        *,
        idempotency_key: str,
        source: str,
        claims_scanned: int,
        candidates: list[WorkItemCandidate],
        now: datetime | None = None,
    ) -> ScanResult:
        completed_at = int((now or datetime.now(UTC)).timestamp())
        run_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM prevention_scan_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return self._scan_result(existing, replayed=True)

            created = 0
            for candidate in candidates:
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO rep_work_items ("
                    "work_item_id, claim_id, rule_id, title, recommended_action, "
                    "risk_band, priority_score, status, version, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, 'open', 1, ?, ?)",
                    (
                        str(uuid4()),
                        candidate.claim_id,
                        candidate.rule_id,
                        candidate.title,
                        candidate.recommended_action,
                        candidate.risk_band,
                        candidate.priority_score,
                        completed_at,
                        completed_at,
                    ),
                )
                created += int(cursor.rowcount == 1)
                connection.execute(
                    "INSERT OR IGNORE INTO claim_interventions ("
                    "claim_id, rule_id, detected_at, recommended_at"
                    ") VALUES (?, ?, ?, ?)",
                    (
                        candidate.claim_id,
                        candidate.rule_id,
                        completed_at,
                        completed_at,
                    ),
                )
            connection.execute(
                "INSERT INTO prevention_scan_runs ("
                "run_id, idempotency_key, source, completed_at, claims_scanned, "
                "items_created, items_existing) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    idempotency_key,
                    source,
                    completed_at,
                    claims_scanned,
                    created,
                    len(candidates) - created,
                ),
            )
            row = connection.execute(
                "SELECT * FROM prevention_scan_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        assert row is not None
        return self._scan_result(row, replayed=False)

    def list_for_rep(self, rep_user_id: int, *, limit: int = 100) -> QueueSnapshot:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT work_items.*, users.username AS assigned_to "
                "FROM rep_work_items AS work_items "
                "LEFT JOIN users ON users.id = work_items.assigned_rep_user_id "
                "WHERE work_items.status = 'open' "
                "OR work_items.assigned_rep_user_id = ? "
                "ORDER BY CASE work_items.status WHEN 'open' THEN 0 ELSE 1 END, "
                "work_items.priority_score DESC, work_items.created_at, "
                "work_items.claim_id, work_items.rule_id LIMIT ?",
                (rep_user_id, limit),
            ).fetchall()
        items = [self._work_item(row) for row in rows]
        return QueueSnapshot(
            items=items,
            open_count=sum(item.status is WorkItemStatus.OPEN for item in items),
            assigned_count=sum(item.assigned_to is not None for item in items),
        )

    def claim(
        self, work_item_id: str, *, rep_user_id: int, expected_version: int
    ) -> RepWorkItem:
        return self._transition(
            work_item_id,
            rep_user_id=rep_user_id,
            expected_version=expected_version,
            from_status=WorkItemStatus.OPEN,
            to_status=WorkItemStatus.CLAIMED,
        )

    def resolve(
        self, work_item_id: str, *, rep_user_id: int, expected_version: int
    ) -> RepWorkItem:
        return self._transition(
            work_item_id,
            rep_user_id=rep_user_id,
            expected_version=expected_version,
            from_status=WorkItemStatus.CLAIMED,
            to_status=WorkItemStatus.RESOLVED,
        )

    def dismiss(
        self, work_item_id: str, *, rep_user_id: int, expected_version: int
    ) -> RepWorkItem:
        return self._transition(
            work_item_id,
            rep_user_id=rep_user_id,
            expected_version=expected_version,
            from_status=WorkItemStatus.CLAIMED,
            to_status=WorkItemStatus.DISMISSED,
        )

    def _transition(
        self,
        work_item_id: str,
        *,
        rep_user_id: int,
        expected_version: int,
        from_status: WorkItemStatus,
        to_status: WorkItemStatus,
    ) -> RepWorkItem:
        now = int(datetime.now(UTC).timestamp())
        terminal = to_status in {WorkItemStatus.RESOLVED, WorkItemStatus.DISMISSED}
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if from_status is WorkItemStatus.OPEN:
                cursor = connection.execute(
                    "UPDATE rep_work_items SET status = ?, assigned_rep_user_id = ?, "
                    "version = version + 1, updated_at = ? "
                    "WHERE work_item_id = ? AND status = 'open' AND version = ?",
                    (
                        to_status.value,
                        rep_user_id,
                        now,
                        work_item_id,
                        expected_version,
                    ),
                )
            else:
                cursor = connection.execute(
                    "UPDATE rep_work_items SET status = ?, version = version + 1, "
                    "updated_at = ?, resolved_at = ? WHERE work_item_id = ? "
                    "AND status = ? AND assigned_rep_user_id = ? AND version = ?",
                    (
                        to_status.value,
                        now,
                        now if terminal else None,
                        work_item_id,
                        from_status.value,
                        rep_user_id,
                        expected_version,
                    ),
                )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM rep_work_items WHERE work_item_id = ?",
                    (work_item_id,),
                ).fetchone()
                if exists is None:
                    raise KeyError(work_item_id)
                raise PreventionConflictError(
                    "Work item state, version, or assignment changed"
                )
            if to_status is WorkItemStatus.RESOLVED:
                connection.execute(
                    "UPDATE claim_interventions SET recorded_at = "
                    "COALESCE(recorded_at, ?) WHERE (claim_id, rule_id) = ("
                    "SELECT claim_id, rule_id FROM rep_work_items "
                    "WHERE work_item_id = ?)",
                    (now, work_item_id),
                )
            row = connection.execute(
                "SELECT work_items.*, users.username AS assigned_to "
                "FROM rep_work_items AS work_items "
                "LEFT JOIN users ON users.id = work_items.assigned_rep_user_id "
                "WHERE work_items.work_item_id = ?",
                (work_item_id,),
            ).fetchone()
        assert row is not None
        return self._work_item(row)

    def get_by_claim_rule(self, claim_id: str, rule_id: str) -> RepWorkItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT work_items.*, users.username AS assigned_to "
                "FROM rep_work_items AS work_items "
                "LEFT JOIN users ON users.id = work_items.assigned_rep_user_id "
                "WHERE work_items.claim_id = ? AND work_items.rule_id = ?",
                (claim_id, rule_id),
            ).fetchone()
        return self._work_item(row) if row is not None else None

    def first_rep_user_id(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM users WHERE role = 'rep' AND is_active = 1 "
                "ORDER BY username LIMIT 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("No active synthetic representative is available")
        return int(row["id"])

    def begin_golden_path(self, idempotency_key: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO golden_path_runs (idempotency_key, status) "
                "VALUES (?, 'running')",
                (idempotency_key,),
            )
        return cursor.rowcount == 1

    def load_golden_path(self, idempotency_key: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, result_json FROM golden_path_runs "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        if row["status"] != "completed" or row["result_json"] is None:
            raise PreventionConflictError("Golden-path run is already in progress")
        return json.loads(row["result_json"])

    def complete_golden_path(self, idempotency_key: str, result: dict) -> None:
        now = int(datetime.now(UTC).timestamp())
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE golden_path_runs SET status = 'completed', completed_at = ?, "
                "result_json = ? WHERE idempotency_key = ? AND status = 'running'",
                (now, json.dumps(result, sort_keys=True), idempotency_key),
            )
        if cursor.rowcount != 1:
            raise PreventionConflictError("Golden-path run could not be completed")

    def abandon_golden_path(self, idempotency_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM golden_path_runs WHERE idempotency_key = ? "
                "AND status = 'running'",
                (idempotency_key,),
            )

    def readiness(self) -> dict[str, object]:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1 FROM rep_work_items LIMIT 1").fetchone()
                row = connection.execute(
                    "SELECT run_id, source, completed_at, claims_scanned, "
                    "items_created, items_existing FROM prevention_scan_runs "
                    "ORDER BY completed_at DESC, run_id DESC LIMIT 1"
                ).fetchone()
            return {
                "status": "ready",
                "database": "ok",
                "last_scan": dict(row) if row is not None else None,
            }
        except sqlite3.Error:
            return {"status": "not_ready", "database": "unavailable", "last_scan": None}

    @staticmethod
    def _scan_result(row: sqlite3.Row, *, replayed: bool) -> ScanResult:
        return ScanResult(
            run_id=row["run_id"],
            idempotency_key=row["idempotency_key"],
            source=row["source"],
            completed_at=datetime.fromtimestamp(row["completed_at"], UTC),
            claims_scanned=row["claims_scanned"],
            items_created=row["items_created"],
            items_existing=row["items_existing"],
            replayed=replayed,
        )

    @staticmethod
    def _work_item(row: sqlite3.Row) -> RepWorkItem:
        return RepWorkItem(
            work_item_id=row["work_item_id"],
            claim_id=row["claim_id"],
            rule_id=row["rule_id"],
            title=row["title"],
            recommended_action=row["recommended_action"],
            risk_band=row["risk_band"],
            priority_score=row["priority_score"],
            status=row["status"],
            assigned_to=row["assigned_to"],
            version=row["version"],
            created_at=datetime.fromtimestamp(row["created_at"], UTC),
            updated_at=datetime.fromtimestamp(row["updated_at"], UTC),
        )
