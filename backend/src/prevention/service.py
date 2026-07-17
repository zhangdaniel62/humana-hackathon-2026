"""Deterministic population scanner over reviewed Claim Readiness rules."""

from __future__ import annotations

from ..clients.claims import ClaimsRepository
from ..models import (
    ClaimReadinessResultStatus,
    ReadinessFactorSeverity,
    ScanResult,
    WorkItemCandidate,
)
from ..services.claim_readiness import ClaimReadinessService
from .store import PreventionStore


class PreventionScanner:
    def __init__(self, repository: ClaimsRepository, store: PreventionStore) -> None:
        self.repository = repository
        self.readiness = ClaimReadinessService(repository)
        self.store = store

    def scan(
        self,
        *,
        idempotency_key: str,
        source: str,
        limit: int = 500,
    ) -> ScanResult:
        claims = self.repository.list_actionable_claims(limit=limit)
        candidates: dict[tuple[str, str], WorkItemCandidate] = {}
        for claim in claims:
            result = self.readiness.evaluate(claim.claim_id)
            if (
                result.status is not ClaimReadinessResultStatus.SUCCESS
                or result.assessment is None
            ):
                continue
            for factor in result.assessment.factors:
                candidate = WorkItemCandidate(
                    claim_id=claim.claim_id,
                    rule_id=factor.rule_id,
                    title=factor.title,
                    recommended_action=factor.recommended_action,
                    risk_band=(
                        "high"
                        if factor.severity is ReadinessFactorSeverity.HIGH
                        else "warning"
                    ),
                    priority_score=(
                        100
                        if factor.severity is ReadinessFactorSeverity.HIGH
                        else 50
                    ),
                )
                candidates[(candidate.claim_id, candidate.rule_id)] = candidate
        ordered = sorted(
            candidates.values(),
            key=lambda item: (-item.priority_score, item.claim_id, item.rule_id),
        )
        return self.store.persist_scan(
            idempotency_key=idempotency_key,
            source=source,
            claims_scanned=len(claims),
            candidates=ordered,
        )
