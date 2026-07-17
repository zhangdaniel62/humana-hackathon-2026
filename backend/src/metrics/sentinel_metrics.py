from __future__ import annotations

from dataclasses import dataclass

from ..models import AgentEvent, EventType, MetricsBaseline, MetricsSnapshot


@dataclass(frozen=True, slots=True)
class _SessionOutcome:
    duration_seconds: float
    resolved: bool
    repeat_contact: bool
    human_escalation: bool
    first_contact_resolution: bool


class SentinelMetrics:
    def __init__(self, baseline: MetricsBaseline | None = None) -> None:
        self._baseline = baseline or MetricsBaseline()
        self._outcomes: dict[str, _SessionOutcome] = {}
        self._observed_sessions: set[str] = set()
        self._roi_gap_sessions: set[str] = set()
        self._readiness_claims: set[str] = set()
        self._recommended_claims: set[str] = set()
        self._recorded_claims: set[str] = set()

    def record(self, event: AgentEvent) -> None:
        if event.event_type is EventType.SESSION_STARTED:
            self._observed_sessions.add(event.session_id)
        elif event.event_type is EventType.ROI_GAP_DETECTED:
            self._roi_gap_sessions.add(event.session_id)
        elif event.event_type is EventType.DENIAL_RISK_DETECTED and event.claim_id:
            self._readiness_claims.add(event.claim_id)
        elif event.event_type is EventType.INTERVENTION_RECOMMENDED and event.claim_id:
            self._recommended_claims.add(event.claim_id)
        elif event.event_type is EventType.INTERVENTION_RECORDED and event.claim_id:
            self._recorded_claims.add(event.claim_id)

        if event.event_type is not EventType.SESSION_COMPLETED:
            return

        payload = event.payload
        duration_seconds = max(float(payload.get("duration_seconds", 0)), 0)
        resolved = bool(payload.get("resolved", False))
        repeat_contact = bool(payload.get("repeat_contact", False))
        human_escalation = bool(payload.get("human_escalation", False))
        first_contact_resolution = bool(
            payload.get(
                "first_contact_resolution",
                resolved and not repeat_contact and not human_escalation,
            )
        )
        self._outcomes[event.session_id] = _SessionOutcome(
            duration_seconds=duration_seconds,
            resolved=resolved,
            repeat_contact=repeat_contact,
            human_escalation=human_escalation,
            first_contact_resolution=first_contact_resolution,
        )

    def snapshot(self) -> MetricsSnapshot:
        outcomes = list(self._outcomes.values())
        total = len(outcomes)
        roi_gap_rate = (
            len(self._roi_gap_sessions) / len(self._observed_sessions)
            if self._observed_sessions
            else None
        )
        interventions = (
            self._readiness_claims
            & self._recommended_claims
            & self._recorded_claims
        )
        if total == 0:
            return MetricsSnapshot(
                roi_gap_rate=self._rounded(roi_gap_rate),
                at_risk_claims_identified=len(self._readiness_claims),
                corrective_interventions_recorded=len(interventions),
                baseline=self._baseline,
            )

        aht = sum(item.duration_seconds for item in outcomes) / total / 60
        fcr = sum(item.first_contact_resolution for item in outcomes) / total
        repeat = sum(item.repeat_contact for item in outcomes) / total
        escalation = sum(item.human_escalation for item in outcomes) / total

        return MetricsSnapshot(
            completed_sessions=total,
            average_handle_time_minutes=round(aht, 2),
            first_contact_resolution_rate=round(fcr, 4),
            repeat_contact_rate=round(repeat, 4),
            escalation_rate=round(escalation, 4),
            roi_gap_rate=self._rounded(roi_gap_rate),
            at_risk_claims_identified=len(self._readiness_claims),
            corrective_interventions_recorded=len(interventions),
            baseline=self._baseline,
            aht_change_rate=self._relative_change(aht, self._baseline.aht_minutes),
            fcr_change_rate=self._relative_change(fcr, self._baseline.fcr_rate),
            repeat_contact_change_rate=self._relative_change(
                repeat, self._baseline.repeat_contact_rate
            ),
        )

    @staticmethod
    def _relative_change(current: float, baseline: float | None) -> float | None:
        if baseline is None or baseline == 0:
            return None
        return round((current - baseline) / baseline, 4)

    @staticmethod
    def _rounded(value: float | None) -> float | None:
        return None if value is None else round(value, 4)
