"""Read-only dashboard projections over the local synthetic operations history."""

from __future__ import annotations

import sqlite3
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from ..models import (
    InterventionFunnel,
    MetricsBaseline,
    OperationsDashboard,
    OperationsDashboardMetadata,
    OperationsMetricSummary,
    OperationsTrendPoint,
    RepWorkload,
)

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_REPEAT_WINDOW = timedelta(days=7)
_REPEAT_WINDOW_SECONDS = int(_REPEAT_WINDOW.total_seconds())


class OperationsStore:
    """Own the synthetic operations tables in the same SQLite file as auth."""

    def __init__(
        self,
        database_path: Path,
        datasets_dir: Path,
        *,
        baseline: MetricsBaseline | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.datasets_dir = Path(datasets_dir)
        self.baseline = baseline or MetricsBaseline(
            aht_minutes=8.5,
            fcr_rate=0.72,
            repeat_contact_rate=0.18,
            source_note="Labeled synthetic hackathon comparison assumptions",
        )

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self, *, enable_demo_seed: bool = True) -> None:
        """Create the operations schema and optionally add its deterministic seed."""

        with self._connect() as connection:
            connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            if enable_demo_seed:
                from .seed import seed_synthetic_operations

                seed_synthetic_operations(connection, self.datasets_dir)

    def dashboard(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        bucket: Literal["week", "month"] = "week",
        now: datetime | None = None,
    ) -> OperationsDashboard:
        """Calculate the manager dashboard from persisted synthetic facts."""

        if bucket not in {"week", "month"}:
            raise ValueError("bucket must be 'week' or 'month'")

        with self._connect() as connection:
            all_calls = connection.execute(
                "SELECT session_id, started_at, duration_seconds, member_id, "
                "claim_id, handling_mode, rep_user_id, resolved "
                "FROM call_sessions ORDER BY started_at, session_id"
            ).fetchall()
            bounds = connection.execute(
                "SELECT MIN(event_at) AS first_at, MAX(event_at) AS last_at FROM ("
                "SELECT started_at AS event_at FROM call_sessions "
                "UNION ALL SELECT detected_at AS event_at FROM claim_interventions"
                ")"
            ).fetchone()

            default_day = (now or datetime.now(UTC)).astimezone(UTC).date()
            first_day = self._date_from_timestamp(bounds["first_at"]) or default_day
            last_day = self._date_from_timestamp(bounds["last_at"]) or first_day
            current_timestamp = int(
                (now or datetime.now(UTC)).astimezone(UTC).timestamp()
            )
            latest_call_at = all_calls[-1]["started_at"] if all_calls else None
            observation_timestamp = (
                min(current_timestamp, latest_call_at)
                if latest_call_at is not None
                else None
            )
            default_end = last_day
            if observation_timestamp is not None:
                completed_period_end = self._completed_period_end(
                    observation_timestamp, bucket
                )
                if completed_period_end >= first_day:
                    default_end = completed_period_end
            selected_start = start or first_day
            selected_end = end or default_end
            if selected_start > selected_end:
                raise ValueError("start must be on or before end")

            start_at = self._day_start_timestamp(selected_start)
            end_at = self._day_start_timestamp(selected_end + timedelta(days=1))
            selected_calls = [
                row for row in all_calls if start_at <= row["started_at"] < end_at
            ]

            outcomes = self._contact_outcomes(all_calls, observation_timestamp)

            summary = self._metric_summary(selected_calls, outcomes)
            grouped: dict[date, list[sqlite3.Row]] = defaultdict(list)
            for row in selected_calls:
                period = self._period_start(row["started_at"], bucket)
                grouped[period].append(row)
            trend = [
                OperationsTrendPoint(
                    period_start=period,
                    **self._metric_summary(rows, outcomes).model_dump(),
                )
                for period, rows in sorted(grouped.items())
            ]

            intervention_row = connection.execute(
                "SELECT COUNT(DISTINCT claim_id) AS identified, "
                "COUNT(DISTINCT CASE WHEN recommended_at IS NOT NULL "
                "THEN claim_id END) AS recommended, "
                "COUNT(DISTINCT CASE WHEN recorded_at IS NOT NULL "
                "THEN claim_id END) AS recorded "
                "FROM claim_interventions WHERE detected_at >= ? AND detected_at < ?",
                (start_at, end_at),
            ).fetchone()
            identified = int(intervention_row["identified"])
            recorded = int(intervention_row["recorded"])
            interventions = InterventionFunnel(
                identified_claims=identified,
                recommended_claims=int(intervention_row["recommended"]),
                recorded_claims=recorded,
                recorded_coverage_rate=(
                    round(recorded / identified, 4) if identified else None
                ),
            )

            rep_rows = connection.execute(
                "SELECT users.username, COUNT(*) AS call_count "
                "FROM call_sessions JOIN users ON users.id = call_sessions.rep_user_id "
                "WHERE call_sessions.handling_mode = 'manual_review' "
                "AND call_sessions.started_at >= ? AND call_sessions.started_at < ? "
                "GROUP BY users.id, users.username "
                "ORDER BY call_count DESC, users.username",
                (start_at, end_at),
            ).fetchall()

        return OperationsDashboard(
            metadata=OperationsDashboardMetadata(
                start=selected_start,
                end=selected_end,
                bucket=bucket,
                observation_cutoff=(
                    datetime.fromtimestamp(observation_timestamp, UTC)
                    if observation_timestamp is not None
                    else None
                ),
            ),
            baseline=self.baseline,
            summary=summary,
            trend=trend,
            interventions=interventions,
            manual_by_rep=[
                RepWorkload(
                    username=row["username"],
                    manual_review_calls=int(row["call_count"]),
                )
                for row in rep_rows
            ],
        )

    @staticmethod
    def _contact_outcomes(
        calls: list[sqlite3.Row], observation_timestamp: int | None
    ) -> dict[str, tuple[bool, bool, bool]]:
        """Return session -> (initial contact, mature cohort, has repeat)."""

        times_by_contact: dict[tuple[str, str], list[int]] = defaultdict(list)
        for row in calls:
            times_by_contact[(row["member_id"], row["claim_id"])].append(
                row["started_at"]
            )

        outcomes: dict[str, tuple[bool, bool, bool]] = {}
        for row in calls:
            started_at = row["started_at"]
            times = times_by_contact[(row["member_id"], row["claim_id"])]
            insertion_index = bisect_left(times, started_at)
            has_recent_prior = (
                insertion_index > 0
                and times[insertion_index - 1]
                >= started_at - _REPEAT_WINDOW_SECONDS
            )
            initial = not has_recent_prior
            mature = bool(
                initial
                and observation_timestamp is not None
                and started_at <= observation_timestamp - _REPEAT_WINDOW_SECONDS
            )
            later_index = bisect_right(times, started_at)
            has_repeat = bool(
                later_index < len(times)
                and times[later_index] <= started_at + _REPEAT_WINDOW_SECONDS
            )
            outcomes[row["session_id"]] = (initial, mature, has_repeat)
        return outcomes

    @staticmethod
    def _metric_summary(
        calls: list[sqlite3.Row],
        outcomes: dict[str, tuple[bool, bool, bool]],
    ) -> OperationsMetricSummary:
        mature_initial = [
            row for row in calls if outcomes[row["session_id"]][1]
        ]
        mature_count = len(mature_initial)
        repeats = sum(
            outcomes[row["session_id"]][2] for row in mature_initial
        )
        first_contact_resolutions = sum(
            bool(row["resolved"]) and not outcomes[row["session_id"]][2]
            for row in mature_initial
        )
        total = len(calls)
        return OperationsMetricSummary(
            completed_sessions=total,
            average_handle_time_minutes=(
                round(
                    sum(row["duration_seconds"] for row in calls) / total / 60,
                    2,
                )
                if total
                else None
            ),
            mature_initial_contacts=mature_count,
            first_contact_resolution_rate=(
                round(first_contact_resolutions / mature_count, 4)
                if mature_count
                else None
            ),
            repeat_contact_rate=(
                round(repeats / mature_count, 4) if mature_count else None
            ),
            automated_calls=sum(
                row["handling_mode"] == "automated" for row in calls
            ),
            manual_review_calls=sum(
                row["handling_mode"] == "manual_review" for row in calls
            ),
        )

    @staticmethod
    def _period_start(
        timestamp: int, bucket: Literal["week", "month"]
    ) -> date:
        value = datetime.fromtimestamp(timestamp, UTC).date()
        if bucket == "month":
            return value.replace(day=1)
        return value - timedelta(days=value.weekday())

    @staticmethod
    def _completed_period_end(
        timestamp: int, bucket: Literal["week", "month"]
    ) -> date:
        value = datetime.fromtimestamp(timestamp, UTC).date()
        if bucket == "month":
            return value.replace(day=1) - timedelta(days=1)
        return value - timedelta(days=value.weekday() + 1)

    @staticmethod
    def _day_start_timestamp(value: date) -> int:
        return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp())

    @staticmethod
    def _date_from_timestamp(value: int | None) -> date | None:
        return datetime.fromtimestamp(value, UTC).date() if value is not None else None
