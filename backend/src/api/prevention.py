"""Authorized proactive-scan and representative queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth.dependencies import CurrentUser, require_capability, require_role
from ..auth.models import Capability, UserRole
from ..clients.claims import ClaimsRepositoryError
from ..models import (
    DelegationTrace,
    QueueSnapshot,
    RepWorkItem,
    ScanRequest,
    ScanResult,
    WorkItemTransitionRequest,
)
from ..prevention import PreventionConflictError

router = APIRouter(prefix="/api", tags=["prevention"])
manager_only = Depends(require_role(UserRole.MANAGER))
rep_queue = Depends(require_capability(Capability.REP_QUEUE))


@router.post(
    "/prevention/scans",
    response_model=ScanResult,
    dependencies=[manager_only],
)
def run_prevention_scan(request: Request, payload: ScanRequest) -> ScanResult:
    try:
        return request.app.state.prevention_scanner.scan(
            idempotency_key=payload.idempotency_key,
            source="manager",
            limit=payload.limit,
        )
    except ClaimsRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The claim population is temporarily unavailable",
        ) from exc


@router.get(
    "/rep/work-items",
    response_model=QueueSnapshot,
    dependencies=[rep_queue],
)
def list_rep_work_items(
    request: Request,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> QueueSnapshot:
    return request.app.state.prevention_store.list_for_rep(user.id, limit=limit)


def _transition(
    request: Request,
    user: CurrentUser,
    work_item_id: str,
    payload: WorkItemTransitionRequest,
    action: str,
) -> RepWorkItem:
    try:
        method = getattr(request.app.state.prevention_store, action)
        return method(
            work_item_id,
            rep_user_id=user.id,
            expected_version=payload.expected_version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Work item not found") from exc
    except PreventionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="Work item state, version, or assignment changed",
        ) from exc


@router.post(
    "/rep/work-items/{work_item_id}/claim",
    response_model=RepWorkItem,
    dependencies=[rep_queue],
)
def claim_work_item(
    work_item_id: str,
    request: Request,
    payload: WorkItemTransitionRequest,
    user: CurrentUser,
) -> RepWorkItem:
    return _transition(request, user, work_item_id, payload, "claim")


@router.post(
    "/rep/work-items/{work_item_id}/resolve",
    response_model=RepWorkItem,
    dependencies=[rep_queue],
)
def resolve_work_item(
    work_item_id: str,
    request: Request,
    payload: WorkItemTransitionRequest,
    user: CurrentUser,
) -> RepWorkItem:
    return _transition(request, user, work_item_id, payload, "resolve")


@router.post(
    "/rep/work-items/{work_item_id}/dismiss",
    response_model=RepWorkItem,
    dependencies=[rep_queue],
)
def dismiss_work_item(
    work_item_id: str,
    request: Request,
    payload: WorkItemTransitionRequest,
    user: CurrentUser,
) -> RepWorkItem:
    return _transition(request, user, work_item_id, payload, "dismiss")


@router.get("/runtime/readiness", dependencies=[manager_only])
def runtime_readiness(request: Request) -> dict[str, object]:
    return request.app.state.prevention_store.readiness()


@router.get(
    "/delegation/traces",
    response_model=list[DelegationTrace],
    dependencies=[manager_only],
)
def list_delegation_traces(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DelegationTrace]:
    return request.app.state.delegation_trace_store.list(limit=limit)
