from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from ..models import AgentEvent, EventType


class EventSubscription:
    def __init__(
        self,
        event_log: EventLog,
        queue: asyncio.Queue[AgentEvent | None],
    ) -> None:
        self._event_log = event_log
        self._queue = queue
        self._closed = False

    async def get(self) -> AgentEvent | None:
        return await self._queue.get()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._event_log._unsubscribe(self._queue)
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            # A bounded subscriber must still be stoppable even under backpressure.
            self._queue.get_nowait()
            self._queue.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[AgentEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[AgentEvent]:
        while True:
            event = await self.get()
            if event is None:
                break
            yield event


class EventLog:
    """Append-only in-process event topic with non-blocking fan-out."""

    def __init__(self) -> None:
        self._events: list[AgentEvent] = []
        self._subscribers: set[asyncio.Queue[AgentEvent | None]] = set()
        self._dropped_events = 0

    @property
    def events(self) -> tuple[AgentEvent, ...]:
        return tuple(self._events)

    @property
    def dropped_events(self) -> int:
        return self._dropped_events

    def subscribe(
        self,
        *,
        replay_existing: bool = False,
        max_queue_size: int = 0,
    ) -> EventSubscription:
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        if replay_existing:
            for event in self._events:
                self._put_without_blocking(queue, event)
        return EventSubscription(self, queue)

    def publish_nowait(self, event: AgentEvent) -> None:
        self._events.append(event)
        for queue in tuple(self._subscribers):
            self._put_without_blocking(queue, event)

    async def publish(self, event: AgentEvent) -> None:
        self.publish_nowait(event)

    def emit(
        self,
        *,
        session_id: str,
        agent: str,
        event_type: EventType | str,
        payload: dict[str, Any] | None = None,
        member_id: str | None = None,
        claim_id: str | None = None,
    ) -> AgentEvent:
        """Create and publish one typed event without blocking the caller path."""

        event = AgentEvent(
            session_id=session_id,
            agent=agent,
            event_type=event_type,
            member_id=member_id,
            claim_id=claim_id,
            payload=payload or {},
        )
        self.publish_nowait(event)
        return event

    def all(self) -> list[AgentEvent]:
        return list(self._events)

    def of_type(self, event_type: EventType | str) -> list[AgentEvent]:
        return [event for event in self._events if event.event_type == event_type]

    def clear(self) -> None:
        self._events.clear()

    def _put_without_blocking(
        self,
        queue: asyncio.Queue[AgentEvent | None],
        event: AgentEvent,
    ) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped_events += 1

    def _unsubscribe(self, queue: asyncio.Queue[AgentEvent | None]) -> None:
        self._subscribers.discard(queue)
