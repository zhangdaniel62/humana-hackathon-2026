"""Deterministic synthetic operational history for local dashboard demos.

The tracked claims CSV remains the source of truth for claim/member identity and
readiness facts. This module only adds call activity and intervention workflow
timestamps to the local SQLite database.
"""

from __future__ import annotations

import csv
import math
import random
import sqlite3
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

_REP_USERNAMES = ("rep.alex", "rep.jordan", "rep.morgan", "rep.taylor")
_WEEK_COUNT = 26
_DAY_WEIGHTS = (20, 20, 20, 20, 20, 5, 3)


def seed_synthetic_operations(
    connection: sqlite3.Connection,
    datasets_dir: Path,
    *,
    anchor_date: date = date(2026, 7, 15),
    random_seed: int = 20260717,
) -> None:
    """Add realistic, repeatable operational history without changing source data.

    Session claim/member pairs always come directly from ``claims.csv``. Follow-up
    contacts are separate rows for the same pair within six days, allowing the
    metrics store to derive repeat contact rather than trusting a seeded flag.
    Inserts use stable identifiers and a savepoint, so rerunning the seed is safe.
    """

    claims = _load_claims(Path(datasets_dir) / "claims.csv")
    rep_ids = _load_rep_ids(connection)
    sessions, first_week_start = _build_sessions(
        claims,
        rep_ids,
        anchor_date=anchor_date,
        random_seed=random_seed,
    )
    interventions = _build_interventions(
        claims,
        first_week_start=first_week_start,
        anchor_date=anchor_date,
        random_seed=random_seed,
    )

    savepoint = "synthetic_operations_seed"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        connection.executemany(
            """
            INSERT OR IGNORE INTO call_sessions (
                session_id,
                started_at,
                duration_seconds,
                member_id,
                claim_id,
                handling_mode,
                rep_user_id,
                resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sessions,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO claim_interventions (
                claim_id,
                rule_id,
                detected_at,
                recommended_at,
                recorded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            interventions,
        )
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
    else:
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")


def _load_claims(path: Path) -> list[dict[str, str]]:
    required_columns = {
        "claim_id",
        "member_id",
        "claim_status",
        "referral_on_file",
        "prior_auth_required",
        "prior_auth_obtained",
    }
    with path.open(newline="", encoding="utf-8") as claim_file:
        reader = csv.DictReader(claim_file)
        missing = required_columns.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"{path} is missing required columns: {', '.join(sorted(missing))}"
            )
        claims = list(reader)

    if not claims:
        raise ValueError(f"{path} contains no claims")

    seen_claim_ids: set[str] = set()
    for claim in claims:
        claim_id = claim["claim_id"].strip()
        member_id = claim["member_id"].strip()
        if not claim_id or not member_id:
            raise ValueError(f"{path} contains a blank claim_id or member_id")
        if claim_id in seen_claim_ids:
            raise ValueError(f"{path} contains duplicate claim_id {claim_id}")
        seen_claim_ids.add(claim_id)
        claim["claim_id"] = claim_id
        claim["member_id"] = member_id
    return claims


def _load_rep_ids(connection: sqlite3.Connection) -> list[int]:
    rep_ids: list[int] = []
    for username in _REP_USERNAMES:
        row = connection.execute(
            "SELECT id, role FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Synthetic operations seed requires demo user {username!r}"
            )
        user_id, role = int(row[0]), str(row[1])
        if role != "rep":
            raise ValueError(f"Demo user {username!r} must have the rep role")
        rep_ids.append(user_id)
    return rep_ids


def _build_sessions(
    claims: list[dict[str, str]],
    rep_ids: list[int],
    *,
    anchor_date: date,
    random_seed: int,
) -> tuple[list[tuple[object, ...]], date]:
    rng = random.Random(random_seed)
    claim_pool = list(claims)
    rng.shuffle(claim_pool)

    # Use the latest completed Monday-Sunday week at or before the anchor. This
    # keeps all generated sessions at or before the requested anchor date.
    last_week_end = anchor_date - timedelta(days=(anchor_date.weekday() + 1) % 7)
    first_week_start = last_week_end - timedelta(
        days=(_WEEK_COUNT - 1) * 7 + 6
    )

    sessions: list[tuple[object, ...]] = []
    claim_index = 0
    manual_assignment_index = 0

    for week_index in range(_WEEK_COUNT):
        progress = week_index / (_WEEK_COUNT - 1)
        week_start = first_week_start + timedelta(weeks=week_index)
        base_count = 46 + round(8 * progress) + rng.randint(-3, 3)

        # Improvement is directional, not monotonic: the sine terms and sampled
        # duration noise create credible week-to-week reversals.
        automated_duration_mean = (
            500
            - 140 * progress
            + 22 * math.sin(week_index * 1.65)
            + rng.uniform(-10, 10)
        )
        manual_probability = _clamp(
            0.30
            - 0.06 * progress
            + 0.025 * math.sin(week_index * 1.2 + 0.4),
            0.20,
            0.34,
        )
        repeat_probability = _clamp(
            0.23
            - 0.13 * progress
            + 0.025 * math.sin(week_index * 1.45 + 0.8),
            0.07,
            0.27,
        )
        nonrepeat_resolution_probability = _clamp(
            0.78
            + 0.16 * progress
            + 0.025 * math.sin(week_index * 1.1 + 0.2),
            0.74,
            0.96,
        )

        for sequence in range(base_count):
            claim = claim_pool[claim_index % len(claim_pool)]
            claim_index += 1
            day_offset = rng.choices(range(7), weights=_DAY_WEIGHTS, k=1)[0]
            session_day = week_start + timedelta(days=day_offset)
            started_at = _business_timestamp(session_day, rng)

            is_manual = rng.random() < manual_probability
            rep_user_id: int | None = None
            handling_mode = "automated"
            if is_manual:
                handling_mode = "manual_review"
                rep_user_id = rep_ids[manual_assignment_index % len(rep_ids)]
                manual_assignment_index += 1

            max_repeat_delay = min(6, (anchor_date - session_day).days)
            will_repeat = (
                max_repeat_delay >= 1 and rng.random() < repeat_probability
            )
            repeat_delay = rng.randint(1, max_repeat_delay) if will_repeat else None

            duration_mean = automated_duration_mean + (155 if is_manual else 0)
            duration_seconds = round(_clamp(rng.gauss(duration_mean, 68), 180, 900))
            if will_repeat:
                resolution_probability = 0.16 + 0.08 * progress
            else:
                resolution_probability = nonrepeat_resolution_probability
            if is_manual:
                resolution_probability += 0.02
            resolved = int(rng.random() < _clamp(resolution_probability, 0, 0.98))

            session_id = f"syn-call-w{week_index:02d}-{sequence:03d}"
            sessions.append(
                (
                    session_id,
                    started_at,
                    duration_seconds,
                    claim["member_id"],
                    claim["claim_id"],
                    handling_mode,
                    rep_user_id,
                    resolved,
                )
            )

            if repeat_delay is not None:
                repeat_day = session_day + timedelta(days=repeat_delay)
                repeat_started_at = _business_timestamp(repeat_day, rng)
                repeat_is_manual = rng.random() < _clamp(
                    manual_probability + 0.14, 0, 0.55
                )
                repeat_rep_user_id: int | None = None
                repeat_mode = "automated"
                if repeat_is_manual:
                    repeat_mode = "manual_review"
                    repeat_rep_user_id = rep_ids[
                        manual_assignment_index % len(rep_ids)
                    ]
                    manual_assignment_index += 1
                repeat_duration_mean = automated_duration_mean * 0.78 + (
                    145 if repeat_is_manual else 0
                )
                repeat_duration = round(
                    _clamp(rng.gauss(repeat_duration_mean, 58), 150, 780)
                )
                repeat_resolved = int(
                    rng.random()
                    < _clamp(0.83 + 0.11 * progress, 0.83, 0.96)
                )
                sessions.append(
                    (
                        f"{session_id}-r1",
                        repeat_started_at,
                        repeat_duration,
                        claim["member_id"],
                        claim["claim_id"],
                        repeat_mode,
                        repeat_rep_user_id,
                        repeat_resolved,
                    )
                )

    return sessions, first_week_start


def _build_interventions(
    claims: list[dict[str, str]],
    *,
    first_week_start: date,
    anchor_date: date,
    random_seed: int,
) -> list[tuple[object, ...]]:
    candidates: list[tuple[str, str]] = []
    for claim in claims:
        if claim["claim_status"].strip().casefold() not in {"pending", "in review"}:
            continue
        if _csv_bool(claim["prior_auth_required"]) and not _csv_bool(
            claim["prior_auth_obtained"]
        ):
            candidates.append((claim["claim_id"], "MISSING_REQUIRED_PRIOR_AUTH"))
        if not _csv_bool(claim["referral_on_file"]):
            candidates.append((claim["claim_id"], "REFERRAL_ON_FILE_WARNING"))

    candidates.sort()
    rng = random.Random(random_seed + 1)
    latest_detection_date = max(first_week_start, anchor_date - timedelta(days=5))
    available_days = (latest_detection_date - first_week_start).days
    interventions: list[tuple[object, ...]] = []

    for index, (claim_id, rule_id) in enumerate(candidates):
        fraction = index / max(1, len(candidates) - 1)
        detected_day = first_week_start + timedelta(
            days=round(available_days * fraction)
        )
        detected_at = _business_timestamp(detected_day, rng)

        # A small, stable share remains at each funnel stage so the dashboard
        # demonstrates detected, recommended, and completed intervention counts.
        recommended_at: int | None = None
        recorded_at: int | None = None
        if index % 11 != 0:
            recommended_at = detected_at + rng.randint(1, 18) * 3600
            if index % 4 != 0:
                recorded_at = recommended_at + rng.randint(3, 72) * 3600

        interventions.append(
            (claim_id, rule_id, detected_at, recommended_at, recorded_at)
        )
    return interventions


def _business_timestamp(value: date, rng: random.Random) -> int:
    started = datetime.combine(
        value,
        time(hour=rng.randint(8, 17), minute=rng.randrange(0, 60)),
        tzinfo=UTC,
    )
    return int(started.timestamp())


def _csv_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Expected CSV boolean true/false, got {value!r}")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
