"""Read-only operational projections plus the deterministic demo trigger."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import MetricsSnapshot, SentinelAlert, SessionSummary
from ..services.golden_path import run_golden_path
from ..services.session_summary import session_summary_store

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/events")
def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    events = request.app.state.event_log.events[-limit:]
    return [event.model_dump(mode="json") for event in reversed(events)]


@router.get("/alerts", response_model=list[SentinelAlert])
def get_alerts(request: Request) -> list[SentinelAlert]:
    return request.app.state.sentinel.snapshot().alerts


@router.get("/metrics", response_model=MetricsSnapshot)
def get_metrics(request: Request) -> MetricsSnapshot:
    return request.app.state.sentinel.snapshot().metrics


@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
def get_session_summary(session_id: str) -> SessionSummary:
    summary = session_summary_store.get(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Session summary not found")
    return summary


@router.post("/demo/golden-path")
async def trigger_golden_path(request: Request) -> dict:
    result = run_golden_path()
    await asyncio.sleep(0)
    result["operations"] = request.app.state.sentinel.snapshot().model_dump(
        mode="json"
    )
    return result
