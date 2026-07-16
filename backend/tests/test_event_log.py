import asyncio

from src.events import EventLog
from src.models import AgentEvent, EventType


def test_event_log_replays_and_streams_events() -> None:
    async def scenario() -> None:
        event_log = EventLog()
        first = AgentEvent(
            session_id="session-1",
            agent="roi_gatekeeper",
            event_type=EventType.SESSION_STARTED,
        )
        event_log.publish_nowait(first)
        subscription = event_log.subscribe(replay_existing=True)
        second = AgentEvent(
            session_id="session-1",
            agent="roi_gatekeeper",
            event_type=EventType.ROI_GAP_DETECTED,
        )
        event_log.publish_nowait(second)

        assert await subscription.get() == first
        assert await subscription.get() == second
        subscription.close()

    asyncio.run(scenario())
