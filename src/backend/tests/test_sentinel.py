import asyncio
from datetime import datetime, timedelta, timezone

from agents import SentinelAgent
from events import EventLog
from models import AgentEvent, AlertType, EventType
from settings import Settings


NOW = datetime(2026, 7, 16, 15, 0, tzinfo=timezone.utc)


def event(
    event_type: EventType,
    *,
    session: str,
    offset_minutes: int = 0,
    member: str | None = "MBR00001",
    claim: str | None = "CLM000001",
    payload: dict | None = None,
) -> AgentEvent:
    return AgentEvent(
        timestamp=NOW + timedelta(minutes=offset_minutes),
        session_id=session,
        agent="test_agent",
        event_type=event_type,
        member_id=member,
        claim_id=claim,
        payload=payload or {},
    )


def test_detects_denial_spike_and_repeat_contact() -> None:
    sentinel = SentinelAgent(EventLog())
    for index in range(3):
        sentinel.process_event(
            event(
                EventType.DENIAL_EXPLAINED,
                session=f"session-{index}",
                offset_minutes=index,
                member=f"MBR0000{index}",
                claim=f"CLM00000{index}",
                payload={"denial_code": "CO-16"},
            )
        )

    sentinel.process_event(
        event(EventType.DENIAL_EXPLAINED, session="repeat-1", offset_minutes=10)
    )
    sentinel.process_event(
        event(EventType.DENIAL_EXPLAINED, session="repeat-2", offset_minutes=20)
    )
    types = {alert.alert_type for alert in sentinel.snapshot().alerts}
    assert AlertType.DENIAL_SPIKE in types
    assert AlertType.REPEAT_CONTACT in types


def test_detects_roi_frequency_using_async_consumer() -> None:
    async def scenario() -> None:
        event_log = EventLog()
        sentinel = SentinelAgent(
            event_log,
            settings=Settings(roi_gap_threshold=2),
        )
        await sentinel.start()
        for index in range(2):
            event_log.publish_nowait(
                event(
                    EventType.ROI_GAP_DETECTED,
                    session=f"roi-{index}",
                    offset_minutes=index,
                    claim=None,
                )
            )
        await sentinel.stop()
        assert any(
            alert.alert_type is AlertType.ROI_GAP_FREQUENCY
            for alert in sentinel.snapshot().alerts
        )

    asyncio.run(scenario())


def test_duplicate_event_is_only_processed_once() -> None:
    sentinel = SentinelAgent(EventLog())
    duplicated = event(EventType.ESCALATION_TRIGGERED, session="session-1")
    sentinel.process_event(duplicated)
    sentinel.process_event(duplicated)
    snapshot = sentinel.snapshot()
    assert snapshot.processed_event_count == 1
    assert snapshot.active_alert_count == 1
