"""Deterministic, fallback-safe assembly of the complete presentation path."""

from __future__ import annotations

from typing import Any

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
from ..models import AgentEvent, EventType
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
