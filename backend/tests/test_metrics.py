from src.agents import SentinelAgent
from src.events import EventLog
from src.models import AgentEvent, EventType, MetricsBaseline


def readiness_event(event_type: EventType, claim_id: str = "CLM000493") -> AgentEvent:
    return AgentEvent(
        session_id="session-1",
        agent="claim_readiness",
        event_type=event_type,
        member_id="MBR00109",
        claim_id=claim_id,
        payload={
            "rule_id": "MISSING_REQUIRED_PRIOR_AUTH",
            "evidence": {"prior_auth_required": True, "prior_auth_obtained": False},
            "recommended_action": "Attach the required authorization.",
            "event_source": "test",
            "synthetic": True,
            "action": (
                "Attach the required authorization."
                if event_type is EventType.INTERVENTION_RECORDED
                else None
            ),
        },
    )


def test_computes_metrics_from_completed_sessions() -> None:
    sentinel = SentinelAgent(
        EventLog(),
        baseline=MetricsBaseline(
            aht_minutes=10,
            fcr_rate=0.5,
            repeat_contact_rate=0.5,
            source_note="Test assumptions",
        ),
    )
    sentinel.process_event(
        AgentEvent(
            session_id="session-1",
            agent="orchestrator",
            event_type=EventType.SESSION_COMPLETED,
            payload={
                "duration_seconds": 360,
                "resolved": True,
                "repeat_contact": False,
                "human_escalation": False,
            },
        )
    )
    sentinel.process_event(
        AgentEvent(
            session_id="session-2",
            agent="orchestrator",
            event_type=EventType.SESSION_COMPLETED,
            payload={
                "duration_seconds": 600,
                "resolved": False,
                "repeat_contact": True,
                "human_escalation": True,
            },
        )
    )
    sentinel.process_event(
        AgentEvent(
            session_id="session-1",
            agent="orchestrator",
            event_type=EventType.SESSION_STARTED,
        )
    )
    sentinel.process_event(
        AgentEvent(
            session_id="session-1",
            agent="roi_gatekeeper",
            event_type=EventType.ROI_GAP_DETECTED,
        )
    )
    for event_type in (
        EventType.DENIAL_RISK_DETECTED,
        EventType.INTERVENTION_RECOMMENDED,
        EventType.INTERVENTION_RECORDED,
    ):
        sentinel.process_event(readiness_event(event_type))

    metrics = sentinel.snapshot().metrics
    assert metrics.completed_sessions == 2
    assert metrics.average_handle_time_minutes == 8
    assert metrics.first_contact_resolution_rate == 0.5
    assert metrics.repeat_contact_rate == 0.5
    assert metrics.escalation_rate == 0.5
    assert metrics.roi_gap_rate == 1
    assert metrics.at_risk_claims_identified == 1
    assert metrics.corrective_interventions_recorded == 1
    assert metrics.aht_change_rate == -0.2


def test_intervention_requires_correlated_risk_recommendation_and_recording() -> None:
    sentinel = SentinelAgent(EventLog())
    sentinel.process_event(readiness_event(EventType.DENIAL_RISK_DETECTED))
    sentinel.process_event(readiness_event(EventType.INTERVENTION_RECORDED))

    metrics = sentinel.snapshot().metrics

    assert metrics.at_risk_claims_identified == 1
    assert metrics.corrective_interventions_recorded == 0
