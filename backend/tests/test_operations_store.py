"""Synthetic operations persistence and cohort-metric tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest

from src.auth import AuthStore, UserRole
from src.operations import OperationsStore


def _timestamp(day: int, hour: int = 10, minute: int = 0, second: int = 0) -> int:
    return int(datetime(2026, 1, day, hour, minute, second, tzinfo=UTC).timestamp())


def _insert_call(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    started_at: int,
    member_id: str,
    claim_id: str,
    duration_seconds: int = 480,
    handling_mode: str = "automated",
    rep_user_id: int | None = None,
    resolved: int = 1,
) -> None:
    connection.execute(
        "INSERT INTO call_sessions "
        "(session_id, started_at, duration_seconds, member_id, claim_id, "
        "handling_mode, rep_user_id, resolved) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            started_at,
            duration_seconds,
            member_id,
            claim_id,
            handling_mode,
            rep_user_id,
            resolved,
        ),
    )


@pytest.fixture
def operations_store(tmp_path):
    database_path = tmp_path / "local.sqlite3"
    auth = AuthStore(database_path)
    auth.initialize(enable_demo_seed=False)
    rep = auth.create_user("rep.metrics", "test-password", UserRole.REP)
    store = OperationsStore(database_path, tmp_path / "datasets")
    store.initialize(enable_demo_seed=False)
    return store, rep.id


def test_derives_repeat_and_fcr_from_mature_seven_day_cohorts(
    operations_store,
) -> None:
    store, rep_id = operations_store
    seven_days = int(timedelta(days=7).total_seconds())
    with sqlite3.connect(store.database_path) as connection:
        _insert_call(
            connection,
            session_id="exact-initial",
            started_at=_timestamp(1),
            member_id="MBR-A",
            claim_id="CLM-A",
            duration_seconds=420,
        )
        _insert_call(
            connection,
            session_id="exact-repeat",
            started_at=_timestamp(1) + seven_days,
            member_id="MBR-A",
            claim_id="CLM-A",
        )
        _insert_call(
            connection,
            session_id="outside-initial",
            started_at=_timestamp(1, 12),
            member_id="MBR-B",
            claim_id="CLM-B",
            duration_seconds=540,
        )
        _insert_call(
            connection,
            session_id="outside-followup",
            started_at=_timestamp(1, 12) + seven_days + 1,
            member_id="MBR-B",
            claim_id="CLM-B",
        )
        _insert_call(
            connection,
            session_id="manual-resolved",
            started_at=_timestamp(3),
            member_id="MBR-C",
            claim_id="CLM-C",
            duration_seconds=600,
            handling_mode="manual_review",
            rep_user_id=rep_id,
        )
        _insert_call(
            connection,
            session_id="immature",
            started_at=_timestamp(15),
            member_id="MBR-D",
            claim_id="CLM-D",
        )
        _insert_call(
            connection,
            session_id="observation-anchor",
            started_at=_timestamp(20),
            member_id="MBR-E",
            claim_id="CLM-E",
        )

    dashboard = store.dashboard(
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
        now=datetime(2026, 1, 25, tzinfo=UTC),
    )

    assert dashboard.summary.completed_sessions == 3
    assert dashboard.summary.average_handle_time_minutes == 8.67
    assert dashboard.summary.mature_initial_contacts == 3
    assert dashboard.summary.repeat_contact_rate == 0.3333
    assert dashboard.summary.first_contact_resolution_rate == 0.6667
    assert dashboard.summary.automated_calls == 2
    assert dashboard.summary.manual_review_calls == 1
    assert sum(row.manual_review_calls for row in dashboard.manual_by_rep) == 1

    immature = store.dashboard(
        start=date(2026, 1, 15),
        end=date(2026, 1, 15),
        now=datetime(2026, 1, 25, tzinfo=UTC),
    )
    assert immature.summary.mature_initial_contacts == 0
    assert immature.summary.first_contact_resolution_rate is None
    assert immature.summary.repeat_contact_rate is None


def test_schema_rejects_invalid_routing_and_intervention_order(
    operations_store,
) -> None:
    store, rep_id = operations_store
    with sqlite3.connect(store.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_call(
                connection,
                session_id="automated-with-rep",
                started_at=_timestamp(1),
                member_id="MBR-A",
                claim_id="CLM-A",
                rep_user_id=rep_id,
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_call(
                connection,
                session_id="manual-without-rep",
                started_at=_timestamp(1),
                member_id="MBR-A",
                claim_id="CLM-A",
                handling_mode="manual_review",
            )
        with pytest.raises(sqlite3.IntegrityError):
            _insert_call(
                connection,
                session_id="zero-duration",
                started_at=_timestamp(1),
                member_id="MBR-A",
                claim_id="CLM-A",
                duration_seconds=0,
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO claim_interventions "
                "(claim_id, rule_id, detected_at, recommended_at, recorded_at) "
                "VALUES ('CLM-A', 'RULE', 100, NULL, 101)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO claim_interventions "
                "(claim_id, rule_id, detected_at, recommended_at, recorded_at) "
                "VALUES ('CLM-B', 'RULE', 100, 99, NULL)"
            )


def test_intervention_funnel_counts_distinct_claims(operations_store) -> None:
    store, _ = operations_store
    detected = _timestamp(5)
    with sqlite3.connect(store.database_path) as connection:
        connection.executemany(
            "INSERT INTO claim_interventions "
            "(claim_id, rule_id, detected_at, recommended_at, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("CLM-A", "RULE-1", detected, detected, detected + 60),
                ("CLM-A", "RULE-2", detected, detected, None),
                ("CLM-B", "RULE-1", detected, None, None),
            ],
        )

    result = store.dashboard(
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        now=datetime(2026, 2, 1, tzinfo=UTC),
    )

    assert result.interventions.identified_claims == 2
    assert result.interventions.recommended_claims == 1
    assert result.interventions.recorded_claims == 1
    assert result.interventions.recorded_coverage_rate == 0.5


def test_default_range_ends_before_trailing_partial_week(
    operations_store,
) -> None:
    store, _ = operations_store
    with sqlite3.connect(store.database_path) as connection:
        _insert_call(
            connection,
            session_id="complete-week",
            started_at=int(datetime(2026, 1, 5, 10, tzinfo=UTC).timestamp()),
            member_id="MBR-A",
            claim_id="CLM-A",
        )
        _insert_call(
            connection,
            session_id="trailing-monday-followup",
            started_at=int(datetime(2026, 1, 12, 10, tzinfo=UTC).timestamp()),
            member_id="MBR-A",
            claim_id="CLM-A",
        )

    result = store.dashboard(now=datetime(2026, 1, 15, tzinfo=UTC))

    assert result.metadata.end == date(2026, 1, 11)
    assert result.summary.completed_sessions == 1
    assert len(result.trend) == 1
    assert result.summary.repeat_contact_rate == 1
