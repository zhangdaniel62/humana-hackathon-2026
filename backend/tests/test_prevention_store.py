"""Persistence, idempotency, and concurrency tests for the rep queue."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from src.auth import AuthStore, UserRole
from src.models import WorkItemCandidate, WorkItemStatus
from src.prevention import PreventionConflictError, PreventionStore


def _candidate(claim_id: str = "CLM000493") -> WorkItemCandidate:
    return WorkItemCandidate(
        claim_id=claim_id,
        rule_id="MISSING_REQUIRED_PRIOR_AUTH",
        title="Required prior authorization is missing",
        recommended_action="Confirm and attach the required prior authorization.",
        risk_band="high",
        priority_score=100,
    )


def _stores(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    auth = AuthStore(database)
    auth.initialize(enable_demo_seed=False)
    rep_one = auth.create_user("rep.one", "test-password", UserRole.REP)
    rep_two = auth.create_user("rep.two", "test-password", UserRole.REP)
    store = PreventionStore(database)
    store.initialize()
    return store, rep_one, rep_two


def test_scan_and_queue_survive_store_reopen_and_retry(tmp_path) -> None:
    store, rep_one, _ = _stores(tmp_path)

    first = store.persist_scan(
        idempotency_key="scan-1",
        source="manager",
        claims_scanned=1,
        candidates=[_candidate()],
    )
    retry = PreventionStore(store.database_path).persist_scan(
        idempotency_key="scan-1",
        source="manager",
        claims_scanned=999,
        candidates=[],
    )
    queue = PreventionStore(store.database_path).list_for_rep(rep_one.id)

    assert first.items_created == 1
    assert retry.run_id == first.run_id
    assert retry.claims_scanned == 1
    assert retry.replayed is True
    assert len(queue.items) == 1
    assert queue.items[0].status is WorkItemStatus.OPEN


def test_database_enforces_scan_and_work_item_deduplication(tmp_path) -> None:
    store, _, _ = _stores(tmp_path)

    def persist(key: str):
        return store.persist_scan(
            idempotency_key=key,
            source="manager",
            claims_scanned=1,
            candidates=[_candidate()],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(persist, ["concurrent", "concurrent"]))
    second_key = persist("different-key")

    assert {result.run_id for result in results}.__len__() == 1
    assert sum(not result.replayed for result in results) == 1
    assert second_key.items_created == 0
    assert second_key.items_existing == 1


def test_claim_race_and_assignee_only_terminal_transition(tmp_path) -> None:
    store, rep_one, rep_two = _stores(tmp_path)
    store.persist_scan(
        idempotency_key="scan-1",
        source="manager",
        claims_scanned=1,
        candidates=[_candidate()],
    )
    item = store.list_for_rep(rep_one.id).items[0]

    claimed = store.claim(
        item.work_item_id, rep_user_id=rep_one.id, expected_version=item.version
    )
    with pytest.raises(PreventionConflictError):
        store.claim(
            item.work_item_id,
            rep_user_id=rep_two.id,
            expected_version=item.version,
        )
    with pytest.raises(PreventionConflictError):
        store.resolve(
            item.work_item_id,
            rep_user_id=rep_two.id,
            expected_version=claimed.version,
        )

    resolved = store.resolve(
        item.work_item_id,
        rep_user_id=rep_one.id,
        expected_version=claimed.version,
    )
    assert resolved.status is WorkItemStatus.RESOLVED
    assert resolved.assigned_to == "rep.one"
    assert resolved.version == 3


def test_readiness_fails_closed_when_database_is_unavailable(tmp_path) -> None:
    store = PreventionStore(tmp_path)

    assert store.readiness() == {
        "status": "not_ready",
        "database": "unavailable",
        "last_scan": None,
    }
