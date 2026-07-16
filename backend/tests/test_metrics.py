from src.agents import SentinelAgent
from src.events import EventLog
from src.models import AgentEvent, EventType, MetricsBaseline


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
                "preventable_denial_caught": True,
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

    metrics = sentinel.snapshot().metrics
    assert metrics.completed_sessions == 2
    assert metrics.average_handle_time_minutes == 8
    assert metrics.first_contact_resolution_rate == 0.5
    assert metrics.repeat_contact_rate == 0.5
    assert metrics.preventable_denials_caught == 1
    assert metrics.aht_change_rate == -0.2
