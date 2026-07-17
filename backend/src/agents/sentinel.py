"""
Sentinel integration contract.

Purpose:
Sentinel is an asynchronous operational/compliance monitor. It must never sit
in the member-response path and must never generate member-facing answers.

Runtime requirements:
- The application must create exactly one shared EventLog.
- SentinelAgent and every event-producing agent must use that same EventLog.
- Start Sentinel during FastAPI/ADK application startup.
- Stop Sentinel during application shutdown.
- Agents should publish events with event_log.publish_nowait(...).
- Agents must not create separate EventLog instances.

Events expected from other agents:

1. Claim Story Agent
   event_type: EventType.DENIAL_EXPLAINED
   required:
       session_id
       member_id
       claim_id
   payload:
       denial_code
       cause_category
       denial_reason (optional)
       provider_id (optional)

2. ROI Gatekeeper
   event_type: EventType.ROI_GAP_DETECTED
   required:
       session_id
       member_id
   payload:
       roi_status
       caller_identity (synthetic identifier only)
       reason

3. Benefits Q&A Agent
   event_type: EventType.COVERAGE_QUESTION_ANSWERED
   required:
       session_id
       member_id
   payload:
       cpt_code
       covered
       prior_auth_required
       grounded_on

4. Orchestrator session start
   event_type: EventType.SESSION_STARTED
   required:
       session_id
       member_id when known
   payload:
       intent (optional)

5. Orchestrator session completion
   event_type: EventType.SESSION_COMPLETED
   required:
       session_id
   payload:
       duration_seconds
       resolved
       repeat_contact
       human_escalation
       first_contact_resolution (optional)

6. Any agent requiring human review
   event_type: EventType.ESCALATION_TRIGGERED
   payload:
       reason
       severity
       recommended_action

7. Compliance-data ingestion
   event_type: EventType.COMPLIANCE_FLAG_DETECTED
   payload:
       flag_type
       severity
       entity_type
       entity_id
       description
       recommended_action

Detection requirements:
- Denial-spike detection needs denial_code or cause_category.
- Repeat-contact detection needs member_id and claim_id across different sessions.
- ROI-frequency detection works best when SESSION_STARTED events are also emitted.
- Operational metrics require valid SESSION_COMPLETED events.
- All event timestamps must be timezone-aware.
- All identifiers and data must be synthetic; never include real PHI.

Frontend contract:
The frontend/dashboard should read sentinel.snapshot() through a read-only API.
The frontend must not modify Sentinel's internal state.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from ..events import EventLog, EventSubscription
from ..metrics import SentinelMetrics
from ..models import (
    AgentEvent,
    AlertSeverity,
    AlertType,
    EventType,
    MetricsBaseline,
    SentinelAlert,
    SentinelSnapshot,
)
from ..settings import SentinelSettings

class SentinelAgent:
    """Consumes agent events asynchronously and maintains explainable risk alerts."""

    _CONTACT_EVENTS = {
        EventType.DENIAL_EXPLAINED,
        EventType.COVERAGE_QUESTION_ANSWERED,
        EventType.ESCALATION_TRIGGERED,
    }

    def __init__(
        self,
        event_log: EventLog,
        *,
        settings: SentinelSettings | None = None,
        baseline: MetricsBaseline | None = None,
    ) -> None:
        self.settings = settings or SentinelSettings()
        self._event_log = event_log
        self._metrics = SentinelMetrics(baseline)
        self._alerts: dict[str, SentinelAlert] = {}
        self._processed_ids: set[UUID] = set()
        self._denials: dict[str, deque[AgentEvent]] = defaultdict(deque)
        self._roi_gaps: deque[AgentEvent] = deque()
        self._session_starts: deque[AgentEvent] = deque()
        self._last_contacts: dict[tuple[str, str], AgentEvent] = {}
        self._subscription: EventSubscription | None = None
        self._consumer_task: asyncio.Task[None] | None = None

    async def start(self, *, replay_existing: bool = True) -> None:
        if self._consumer_task is not None:
            return
        self._subscription = self._event_log.subscribe(
            replay_existing=replay_existing
        )
        self._consumer_task = asyncio.create_task(self._consume())
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self._subscription is not None:
            self._subscription.close()
        if self._consumer_task is not None:
            await self._consumer_task
        self._subscription = None
        self._consumer_task = None

    async def _consume(self) -> None:
        assert self._subscription is not None
        async for event in self._subscription:
            self.process_event(event)

    def process_event(self, event: AgentEvent) -> None:
        if event.event_id in self._processed_ids:
            return
        self._processed_ids.add(event.event_id)
        self._metrics.record(event)

        if event.event_type is EventType.SESSION_STARTED:
            self._record_session_start(event)
        elif event.event_type is EventType.DENIAL_EXPLAINED:
            self._detect_denial_spike(event)
        elif event.event_type is EventType.ROI_GAP_DETECTED:
            self._detect_roi_gap_frequency(event)
        elif event.event_type is EventType.ESCALATION_TRIGGERED:
            self._create_escalation_alert(event)
        elif event.event_type is EventType.COMPLIANCE_FLAG_DETECTED:
            self._create_compliance_alert(event)
        elif event.event_type is EventType.DENIAL_RISK_DETECTED:
            self._create_readiness_alert(event)
        elif event.event_type is EventType.INTERVENTION_RECORDED:
            self._mark_intervention_recorded(event)
        elif event.event_type is EventType.NETWORK_GAP_DETECTED:
            self._create_network_gap_alert(event)

        if event.event_type in self._CONTACT_EVENTS:
            self._detect_repeat_contact(event)

    def snapshot(self) -> SentinelSnapshot:
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
        }
        alerts = sorted(
            (alert for alert in self._alerts.values() if alert.active),
            key=lambda alert: (severity_order[alert.severity], -alert.last_seen.timestamp()),
        )
        return SentinelSnapshot(
            processed_event_count=len(self._processed_ids),
            dropped_event_count=self._event_log.dropped_events,
            active_alert_count=len(alerts),
            alerts=alerts,
            metrics=self._metrics.snapshot(),
        )

    def _record_session_start(self, event: AgentEvent) -> None:
        self._session_starts.append(event)
        self._prune(
            self._session_starts,
            event.timestamp,
            timedelta(hours=self.settings.roi_window_hours),
        )

    def _detect_denial_spike(self, event: AgentEvent) -> None:
        category = str(
            event.payload.get("cause_category")
            or event.payload.get("denial_code")
            or "unknown"
        )
        events = self._denials[category]
        events.append(event)
        window = timedelta(hours=self.settings.denial_window_hours)
        self._prune(events, event.timestamp, window)
        count = len(events)
        if count < self.settings.denial_spike_threshold:
            return

        severity = (
            AlertSeverity.HIGH
            if count >= self.settings.denial_spike_threshold * 2
            else AlertSeverity.MEDIUM
        )
        dedup_key = f"denial_spike:{category}:{event.timestamp.date().isoformat()}"
        self._upsert_alert(
            dedup_key=dedup_key,
            alert_type=AlertType.DENIAL_SPIKE,
            severity=severity,
            title=f"Denial spike: {category}",
            description=(
                f"{count} denial events for {category} occurred within the last "
                f"{self.settings.denial_window_hours} hours."
            ),
            recommended_action=(
                "Review the shared denial cause, affected providers, and whether a "
                "proactive member/provider notification can prevent additional denials."
            ),
            event=event,
            occurrences=count,
            evidence=[item.event_id for item in events],
            metadata={
                "denial_category": category,
                "window_hours": self.settings.denial_window_hours,
                "count": count,
            },
        )

    def _detect_roi_gap_frequency(self, event: AgentEvent) -> None:
        self._roi_gaps.append(event)
        window = timedelta(hours=self.settings.roi_window_hours)
        self._prune(self._roi_gaps, event.timestamp, window)
        self._prune(self._session_starts, event.timestamp, window)

        gap_sessions = {item.session_id for item in self._roi_gaps}
        all_sessions = {item.session_id for item in self._session_starts}
        gap_count = len(gap_sessions)
        session_count = len(all_sessions)
        gap_rate = gap_count / session_count if session_count else None
        threshold_reached = gap_count >= self.settings.roi_gap_threshold
        rate_reached = (
            session_count >= self.settings.roi_minimum_sessions
            and gap_rate is not None
            and gap_rate >= self.settings.roi_gap_rate_threshold
        )
        if not threshold_reached and not rate_reached:
            return

        dedup_key = f"roi_gap_frequency:{event.timestamp.date().isoformat()}"
        rate_text = f" ({gap_rate:.1%} of sessions)" if gap_rate is not None else ""
        self._upsert_alert(
            dedup_key=dedup_key,
            alert_type=AlertType.ROI_GAP_FREQUENCY,
            severity=AlertSeverity.HIGH,
            title="Frequent missing ROI authorizations",
            description=(
                f"{gap_count} unique sessions encountered an ROI gap{rate_text} "
                f"within {self.settings.roi_window_hours} hours."
            ),
            recommended_action=(
                "Review ROI self-service messaging and route unresolved cases through "
                "the approved authorization workflow before disclosing member details."
            ),
            event=event,
            occurrences=gap_count,
            evidence=[item.event_id for item in self._roi_gaps],
            metadata={
                "gap_sessions": gap_count,
                "observed_sessions": session_count,
                "gap_rate": gap_rate,
                "window_hours": self.settings.roi_window_hours,
            },
        )

    def _detect_repeat_contact(self, event: AgentEvent) -> None:
        if not event.member_id or not event.claim_id:
            return
        key = (event.member_id, event.claim_id)
        previous = self._last_contacts.get(key)
        self._last_contacts[key] = event
        if previous is None or previous.session_id == event.session_id:
            return

        elapsed = event.timestamp - previous.timestamp
        if elapsed < timedelta(0) or elapsed > timedelta(
            days=self.settings.repeat_contact_days
        ):
            return

        dedup_key = f"repeat_contact:{event.member_id}:{event.claim_id}"
        self._upsert_alert(
            dedup_key=dedup_key,
            alert_type=AlertType.REPEAT_CONTACT,
            severity=AlertSeverity.MEDIUM,
            title=f"Repeat contact for claim {event.claim_id}",
            description=(
                f"Member {event.member_id} contacted the system about claim "
                f"{event.claim_id} in separate sessions within "
                f"{self.settings.repeat_contact_days} days."
            ),
            recommended_action=(
                "Review the earlier response for unresolved actions and provide a "
                "single consolidated resolution path."
            ),
            event=event,
            evidence=[previous.event_id, event.event_id],
            metadata={
                "member_id": event.member_id,
                "claim_id": event.claim_id,
                "previous_session_id": previous.session_id,
                "current_session_id": event.session_id,
                "hours_between_contacts": round(elapsed.total_seconds() / 3600, 2),
            },
        )

    def _create_escalation_alert(self, event: AgentEvent) -> None:
        reason = str(event.payload.get("reason", "Specialist requested escalation"))
        self._upsert_alert(
            dedup_key=f"escalation:{event.session_id}",
            alert_type=AlertType.ESCALATION,
            severity=self._severity_from_value(
                event.payload.get("severity"), AlertSeverity.HIGH
            ),
            title=f"Escalation in session {event.session_id}",
            description=reason,
            recommended_action=str(
                event.payload.get(
                    "recommended_action",
                    "Route to the appropriate human queue with the event evidence attached.",
                )
            ),
            event=event,
            metadata={"member_id": event.member_id, "claim_id": event.claim_id},
        )

    def _create_compliance_alert(self, event: AgentEvent) -> None:
        flag_type = str(event.payload.get("flag_type", "UNSPECIFIED_COMPLIANCE_FLAG"))
        entity_id = str(event.payload.get("entity_id") or event.member_id or event.claim_id)
        self._upsert_alert(
            dedup_key=f"compliance:{flag_type}:{entity_id}",
            alert_type=AlertType.COMPLIANCE_RISK,
            severity=self._severity_from_value(
                event.payload.get("severity"), AlertSeverity.HIGH
            ),
            title=flag_type.replace("_", " ").title(),
            description=str(event.payload.get("description", "Compliance risk detected")),
            recommended_action=str(
                event.payload.get("recommended_action", "Review and resolve the flag.")
            ),
            event=event,
            metadata={
                key: value
                for key, value in event.payload.items()
                if key not in {"description", "recommended_action"}
            },
        )

    def _create_readiness_alert(self, event: AgentEvent) -> None:
        rule_id = str(event.payload["rule_id"])
        risk_band = str(event.payload.get("risk_band", "warning"))
        severity = (
            AlertSeverity.HIGH if risk_band == "high" else AlertSeverity.MEDIUM
        )
        self._upsert_alert(
            dedup_key=f"claim_readiness:{event.claim_id}:{rule_id}",
            alert_type=AlertType.CLAIM_READINESS_RISK,
            severity=severity,
            title=f"Claim Readiness finding for {event.claim_id}",
            description=(
                f"Reviewed rule {rule_id} matched the synthetic claim evidence."
            ),
            recommended_action=str(event.payload["recommended_action"]),
            event=event,
            metadata={
                "claim_id": event.claim_id,
                "member_id": event.member_id,
                "rule_id": rule_id,
                "evidence": event.payload["evidence"],
                "event_source": event.payload["event_source"],
                "synthetic": event.payload["synthetic"],
                "intervention_recorded": False,
            },
        )

    def _mark_intervention_recorded(self, event: AgentEvent) -> None:
        key = f"claim_readiness:{event.claim_id}:{event.payload['rule_id']}"
        alert = self._alerts.get(key)
        if alert is None:
            return
        metadata = {
            **alert.metadata,
            "intervention_recorded": True,
            "recorded_action": event.payload.get("action"),
        }
        self._alerts[key] = alert.model_copy(
            update={
                "last_seen": event.timestamp,
                "evidence_event_ids": [
                    *alert.evidence_event_ids,
                    event.event_id,
                ][-self.settings.evidence_limit :],
                "metadata": metadata,
                "recommended_action": (
                    "Verify the recorded correction is attached before final adjudication."
                ),
            }
        )

    def _create_network_gap_alert(self, event: AgentEvent) -> None:
        specialty = str(event.payload.get("specialty", "requested specialty"))
        self._upsert_alert(
            dedup_key=f"network_gap:{event.member_id}:{specialty}",
            alert_type=AlertType.NETWORK_GAP,
            severity=AlertSeverity.MEDIUM,
            title=f"Network access gap: {specialty}",
            description=str(event.payload.get("detail", "Network gap detected")),
            recommended_action=(
                "Review directory capacity and preserve the grounded PCP referral path."
            ),
            event=event,
            metadata=dict(event.payload),
        )

    def _upsert_alert(
        self,
        *,
        dedup_key: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        recommended_action: str,
        event: AgentEvent,
        occurrences: int | None = None,
        evidence: list[UUID] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        prior = self._alerts.get(dedup_key)
        evidence_ids = list(evidence or [event.event_id])[-self.settings.evidence_limit :]
        if prior is not None:
            combined_evidence = list(
                dict.fromkeys([*prior.evidence_event_ids, *evidence_ids])
            )[-self.settings.evidence_limit :]
            self._alerts[dedup_key] = prior.model_copy(
                update={
                    "severity": severity,
                    "description": description,
                    "recommended_action": recommended_action,
                    "last_seen": event.timestamp,
                    "occurrences": occurrences or prior.occurrences + 1,
                    "evidence_event_ids": combined_evidence,
                    "metadata": metadata or prior.metadata,
                }
            )
            return

        self._alerts[dedup_key] = SentinelAlert(
            alert_id=uuid5(NAMESPACE_URL, dedup_key),
            dedup_key=dedup_key,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            recommended_action=recommended_action,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            occurrences=occurrences or 1,
            evidence_event_ids=evidence_ids,
            metadata=metadata or {},
        )

    @staticmethod
    def _prune(
        events: deque[AgentEvent],
        current_time: datetime,
        window: timedelta,
    ) -> None:
        cutoff = current_time - window
        while events and events[0].timestamp < cutoff:
            events.popleft()

    @staticmethod
    def _severity_from_value(
        raw_value: Any,
        default: AlertSeverity,
    ) -> AlertSeverity:
        if raw_value is None:
            return default
        try:
            return AlertSeverity(str(raw_value).lower())
        except ValueError:
            return default
