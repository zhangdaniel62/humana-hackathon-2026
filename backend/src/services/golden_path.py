"""Deterministic, fallback-safe assembly of the complete presentation path."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from ..agents.benefits import lookup_coverage
from ..agents.claim_readiness import (
    build_record_corrective_intervention_tool,
    build_screen_claim_readiness_tool,
)
from ..agents.claim_story import build_lookup_claim_story_tool
from ..agents.session_context import build_establish_member_context_tool
from ..clients.claims import CsvClaimsRepository
from ..clients.member_records import CsvMemberRecordsClient
from ..events import event_log
from ..models import AgentEvent, DelegationTrace, EventType, WorkItemStatus
from ..delegation.store import TraceSink
from ..evaluation import EvaluationHarness
from ..prevention import PreventionConflictError, PreventionScanner, PreventionStore
from .claim_readiness import ClaimReadinessService
from .claim_story import ClaimStoryService
from .session_summary import session_summary_store

GOLDEN_SESSION_ID = "golden-path-session"
GOLDEN_MEMBER_ID = "MBR00109"
GOLDEN_CALLER_NAME = "Ronnie Lee"
GOLDEN_DENIED_CLAIM_ID = "CLM000490"
GOLDEN_READINESS_CLAIM_ID = "CLM000493"
GOLDEN_BENEFIT_QUERY = "70553"


class _ToolContext:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "session_id": GOLDEN_SESSION_ID,
            "caller_id": GOLDEN_MEMBER_ID,
        }


def run_golden_path() -> dict[str, Any]:
    """Run the fixed synthetic story without Vertex AI or BigQuery."""

    repository = CsvClaimsRepository()
    context = _ToolContext()

    roi_tool = build_establish_member_context_tool(
        CsvMemberRecordsClient(), event_log
    )
    claim_tool = build_lookup_claim_story_tool(
        ClaimStoryService(repository),
        enforce_member_context=True,
        events=event_log,
    )
    readiness_tool = build_screen_claim_readiness_tool(
        ClaimReadinessService(repository),
        enforce_member_context=True,
        events=event_log,
    )
    intervention_tool = build_record_corrective_intervention_tool(
        events=event_log
    )

    roi = roi_tool.func(GOLDEN_CALLER_NAME, GOLDEN_MEMBER_ID, context)
    claim = claim_tool.func(GOLDEN_DENIED_CLAIM_ID, context)
    benefits = lookup_coverage(GOLDEN_BENEFIT_QUERY, context)
    readiness = readiness_tool.func(GOLDEN_READINESS_CLAIM_ID, context)
    intervention = intervention_tool.func(GOLDEN_READINESS_CLAIM_ID, context)
    event_log.publish_nowait(
        AgentEvent(
            session_id=GOLDEN_SESSION_ID,
            agent="orchestrator",
            event_type=EventType.SESSION_COMPLETED,
            member_id=GOLDEN_MEMBER_ID,
            payload={
                "duration_seconds": 330,
                "resolved": True,
                "repeat_contact": False,
                "human_escalation": False,
                "synthetic": True,
            },
        )
    )
    session_summary_store.capture(context.state)
    return {
        "status": "complete",
        "data_label": "synthetic_demo_data",
        "session_id": GOLDEN_SESSION_ID,
        "fixed_ids": {
            "member_id": GOLDEN_MEMBER_ID,
            "denied_claim_id": GOLDEN_DENIED_CLAIM_ID,
            "readiness_claim_id": GOLDEN_READINESS_CLAIM_ID,
        },
        "roi": roi,
        "claim_story": claim,
        "benefits": benefits,
        "readiness": readiness,
        "notification_preview": readiness.get("notification_preview"),
        "intervention": intervention,
    }


def run_expanded_golden_path(
    *,
    scanner: PreventionScanner,
    prevention_store: PreventionStore,
    trace_store: TraceSink,
    idempotency_key: str,
) -> dict[str, Any]:
    """Run scanner -> simulated rep work -> grounded fallback -> evaluation once."""

    existing = prevention_store.load_golden_path(idempotency_key)
    if existing is not None:
        return {**existing, "replayed": True}
    if not prevention_store.begin_golden_path(idempotency_key):
        existing = prevention_store.load_golden_path(idempotency_key)
        assert existing is not None
        return {**existing, "replayed": True}

    try:
        scan = scanner.scan(
            idempotency_key=f"golden:{idempotency_key}:scan",
            source="golden_path",
        )
        work_item = prevention_store.get_by_claim_rule(
            GOLDEN_READINESS_CLAIM_ID, "MISSING_REQUIRED_PRIOR_AUTH"
        )
        if work_item is None:
            raise RuntimeError("The golden readiness work item was not produced")
        rep_user_id = prevention_store.first_rep_user_id()
        if work_item.status is WorkItemStatus.OPEN:
            work_item = prevention_store.claim(
                work_item.work_item_id,
                rep_user_id=rep_user_id,
                expected_version=work_item.version,
            )
        if work_item.status is WorkItemStatus.CLAIMED:
            work_item = prevention_store.resolve(
                work_item.work_item_id,
                rep_user_id=rep_user_id,
                expected_version=work_item.version,
            )
        if work_item.status is not WorkItemStatus.RESOLVED:
            raise PreventionConflictError(
                "The golden work item is not available for simulated rep resolution"
            )

        delegation_started = datetime.now(UTC)
        delegation_clock = monotonic()
        base = run_golden_path()
        delegation_completed = datetime.now(UTC)
        trace = DelegationTrace(
            trace_id=str(uuid4()),
            session_id=GOLDEN_SESSION_ID,
            work_item_id=work_item.work_item_id,
            specialist="claim_story_agent",
            started_at=delegation_started,
            completed_at=delegation_completed,
            latency_ms=round((monotonic() - delegation_clock) * 1_000, 3),
            outcome="fallback",
            error_code="offline_demo_mode",
        )
        trace_store.record(trace)

        corpus = Path(__file__).resolve().parents[2] / "evaluation" / "corpus.json"
        evaluation = EvaluationHarness().run(corpus)
        result = {
            **base,
            "workflow_mode": "synthetic_rep_simulation",
            "idempotency_key": idempotency_key,
            "replayed": False,
            "prevention_scan": scan.model_dump(mode="json"),
            "rep_work_item": work_item.model_dump(mode="json"),
            "delegation_trace": trace.model_dump(mode="json"),
            "evaluation": {
                "corpus_version": evaluation.corpus_version,
                "passed": evaluation.passed,
                "total": evaluation.total,
                "pass_rate": evaluation.pass_rate,
                "thresholds_met": evaluation.thresholds_met,
            },
        }
        prevention_store.complete_golden_path(idempotency_key, result)
        return result
    except Exception:
        prevention_store.abandon_golden_path(idempotency_key)
        raise
