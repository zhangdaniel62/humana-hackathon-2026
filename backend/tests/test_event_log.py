import asyncio

from src.agents import SentinelAgent
from src.events import EventLog, SQLiteEventStore
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


def test_sqlite_event_replay_survives_restart_and_is_exactly_once(tmp_path) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    store.initialize()
    original = EventLog(store)
    event = AgentEvent(
        session_id="durable-session",
        agent="orchestrator",
        event_type=EventType.SESSION_STARTED,
        payload={"synthetic": True},
    )
    original.publish_nowait(event)
    original.publish_nowait(event)

    restarted = EventLog(store)

    assert restarted.events == (event,)

    async def replay_twice() -> None:
        sentinel = SentinelAgent(restarted)
        await sentinel.start(replay_existing=True)
        assert sentinel.snapshot().processed_event_count == 1
        await sentinel.stop()
        await sentinel.start(replay_existing=True)
        assert sentinel.snapshot().processed_event_count == 1
        await sentinel.stop()

    asyncio.run(replay_twice())
