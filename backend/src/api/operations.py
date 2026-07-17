"""Read-only operational projections plus the deterministic demo trigger."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth.dependencies import CurrentUser, require_role
from ..auth.models import UserRole
from ..models import (
    MetricsSnapshot,
    GoldenPathRequest,
    OperationsDashboard,
    SentinelAlert,
    SessionSummary,
)
from ..prevention import PreventionConflictError
from ..services.golden_path import run_expanded_golden_path
from ..services.session_summary import session_summary_store

router = APIRouter(prefix="/api", tags=["operations"])
manager_only = Depends(require_role(UserRole.MANAGER))


@router.get("/events", dependencies=[manager_only])
def get_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    events = request.app.state.event_log.events[-limit:]
    return [event.model_dump(mode="json") for event in reversed(events)]


@router.get(
    "/alerts", response_model=list[SentinelAlert], dependencies=[manager_only]
)
def get_alerts(request: Request) -> list[SentinelAlert]:
    return request.app.state.sentinel.snapshot().alerts


@router.get(
    "/metrics", response_model=MetricsSnapshot, dependencies=[manager_only]
)
def get_metrics(request: Request) -> MetricsSnapshot:
    return request.app.state.sentinel.snapshot().metrics


@router.get(
    "/operations/dashboard",
    response_model=OperationsDashboard,
    dependencies=[manager_only],
)
def get_operations_dashboard(
    request: Request,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    bucket: Literal["week", "month"] = Query(default="week"),
) -> OperationsDashboard:
    try:
        return request.app.state.operations_store.dashboard(
            start=start,
            end=end,
            bucket=bucket,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
def get_session_summary(session_id: str, user: CurrentUser) -> SessionSummary:
    summary = session_summary_store.get(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Session summary not found")
    if (
        user.role is UserRole.CUSTOMER
        and session_summary_store.owner_user_id(session_id) != str(user.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return summary


@router.post("/demo/golden-path", dependencies=[manager_only])
async def trigger_golden_path(
    request: Request, payload: GoldenPathRequest | None = None
) -> dict:
    requested = payload or GoldenPathRequest()
    try:
        result = run_expanded_golden_path(
            scanner=request.app.state.prevention_scanner,
            prevention_store=request.app.state.prevention_store,
            trace_store=request.app.state.delegation_trace_store,
            idempotency_key=requested.idempotency_key,
        )
    except PreventionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await asyncio.sleep(0)
    result["operations"] = request.app.state.sentinel.snapshot().model_dump(
        mode="json"
    )
    return result
