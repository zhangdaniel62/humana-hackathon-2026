"""Integrity and behavior checks for the local synthetic operations seed."""

from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.operations.seed import seed_synthetic_operations

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASETS_DIR = _REPO_ROOT / "datasets"
_AUTH_SCHEMA = _REPO_ROOT / "backend" / "src" / "auth" / "schema.sql"
_AUTH_SEED = _REPO_ROOT / "backend" / "src" / "auth" / "demo_seed.sql"
_OPERATIONS_SCHEMA = (
    _REPO_ROOT / "backend" / "src" / "operations" / "schema.sql"
)
_REP_USERNAMES = {"rep.alex", "rep.jordan", "rep.morgan", "rep.taylor"}


@pytest.fixture
def seeded_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_AUTH_SCHEMA.read_text(encoding="utf-8"))
    connection.executescript(_AUTH_SEED.read_text(encoding="utf-8"))
    connection.executescript(_OPERATIONS_SCHEMA.read_text(encoding="utf-8"))
    seed_synthetic_operations(connection, _DATASETS_DIR)
    try:
        yield connection
    finally:
        connection.close()


def test_seed_is_deterministic_idempotent_and_uses_source_pairs(
    seeded_connection: sqlite3.Connection,
) -> None:
    connection = seeded_connection
    first_sessions = connection.execute(
        "SELECT * FROM call_sessions ORDER BY session_id"
    ).fetchall()
    first_interventions = connection.execute(
        "SELECT * FROM claim_interventions ORDER BY claim_id, rule_id"
    ).fetchall()

    seed_synthetic_operations(connection, _DATASETS_DIR)

    assert connection.execute(
        "SELECT * FROM call_sessions ORDER BY session_id"
    ).fetchall() == first_sessions
    assert connection.execute(
        "SELECT * FROM claim_interventions ORDER BY claim_id, rule_id"
    ).fetchall() == first_interventions
    assert len(first_sessions) > 1_400

    with (_DATASETS_DIR / "claims.csv").open(newline="", encoding="utf-8") as file:
        source_pairs = {
            (row["claim_id"], row["member_id"]) for row in csv.DictReader(file)
        }
    seeded_pairs = {
        (row[4], row[3]) for row in first_sessions
    }
    assert seeded_pairs <= source_pairs

    manual_reps = connection.execute(
        "SELECT DISTINCT users.username, users.role "
        "FROM call_sessions JOIN users ON users.id = call_sessions.rep_user_id "
        "WHERE handling_mode = 'manual_review'"
    ).fetchall()
    assert {row[0] for row in manual_reps} == _REP_USERNAMES
    assert {row[1] for row in manual_reps} == {"rep"}
    assert connection.execute(
        "SELECT COUNT(*) FROM call_sessions "
        "WHERE (handling_mode = 'automated' AND rep_user_id IS NOT NULL) "
        "OR (handling_mode = 'manual_review' AND rep_user_id IS NULL)"
    ).fetchone()[0] == 0


def test_repeat_contacts_are_real_followup_rows(
    seeded_connection: sqlite3.Connection,
) -> None:
    repeats = seeded_connection.execute(
        "SELECT session_id, started_at, member_id, claim_id "
        "FROM call_sessions WHERE session_id LIKE '%-r1'"
    ).fetchall()
    assert len(repeats) > 150

    for repeat_id, repeat_at, member_id, claim_id in repeats:
        original = seeded_connection.execute(
            "SELECT started_at, member_id, claim_id FROM call_sessions "
            "WHERE session_id = ?",
            (repeat_id.removesuffix("-r1"),),
        ).fetchone()
        assert original is not None
        original_day = datetime.fromtimestamp(original[0], UTC).date()
        repeat_day = datetime.fromtimestamp(repeat_at, UTC).date()
        assert 1 <= (repeat_day - original_day).days <= 6
        assert (member_id, claim_id) == (original[1], original[2])


def test_interventions_are_justified_by_unchanged_claim_rows(
    seeded_connection: sqlite3.Connection,
) -> None:
    with (_DATASETS_DIR / "claims.csv").open(newline="", encoding="utf-8") as file:
        claims = {row["claim_id"]: row for row in csv.DictReader(file)}

    interventions = seeded_connection.execute(
        "SELECT claim_id, rule_id, detected_at, recommended_at, recorded_at "
        "FROM claim_interventions"
    ).fetchall()
    assert len(interventions) == 26

    for claim_id, rule_id, detected_at, recommended_at, recorded_at in interventions:
        claim = claims[claim_id]
        assert claim["claim_status"] in {"Pending", "In Review"}
        if rule_id == "MISSING_REQUIRED_PRIOR_AUTH":
            assert claim["prior_auth_required"] == "true"
            assert claim["prior_auth_obtained"] == "false"
        elif rule_id == "REFERRAL_ON_FILE_WARNING":
            assert claim["referral_on_file"] == "false"
        else:
            pytest.fail(f"Unexpected synthetic intervention rule {rule_id}")
        assert recommended_at is None or recommended_at >= detected_at
        assert recorded_at is None or (
            recommended_at is not None and recorded_at >= recommended_at
        )


def test_seed_has_noisy_directional_aht_fcr_and_repeat_trends(
    seeded_connection: sqlite3.Connection,
) -> None:
    rows = seeded_connection.execute(
        "SELECT session_id, duration_seconds, resolved FROM call_sessions"
    ).fetchall()
    durations_by_week: dict[int, list[int]] = defaultdict(list)
    bases_by_week: dict[int, dict[str, int]] = defaultdict(dict)
    repeats_by_week: dict[int, int] = defaultdict(int)
    repeat_ids = {
        row[0].removesuffix("-r1") for row in rows if row[0].endswith("-r1")
    }

    for session_id, duration, resolved in rows:
        week_index = int(session_id[10:12])
        durations_by_week[week_index].append(duration)
        if session_id.endswith("-r1"):
            repeats_by_week[week_index] += 1
        else:
            bases_by_week[week_index][session_id] = resolved

    aht: list[float] = []
    fcr: list[float] = []
    repeat_rate: list[float] = []
    for week_index in range(26):
        durations = durations_by_week[week_index]
        bases = bases_by_week[week_index]
        base_count = len(bases)
        aht.append(sum(durations) / len(durations) / 60)
        fcr.append(
            sum(
                bool(resolved) and session_id not in repeat_ids
                for session_id, resolved in bases.items()
            )
            / base_count
        )
        repeat_rate.append(repeats_by_week[week_index] / base_count)

    mean = lambda values: sum(values) / len(values)
    assert mean(aht[:6]) > mean(aht[-6:]) + 1.0
    assert mean(fcr[:6]) + 0.10 < mean(fcr[-6:])
    assert mean(repeat_rate[:6]) > mean(repeat_rate[-6:]) + 0.05

    # Credible noise includes occasional week-over-week setbacks.
    assert any(later > earlier for earlier, later in zip(aht, aht[1:]))
    assert any(later < earlier for earlier, later in zip(fcr, fcr[1:]))
    assert any(
        later > earlier for earlier, later in zip(repeat_rate, repeat_rate[1:])
    )
