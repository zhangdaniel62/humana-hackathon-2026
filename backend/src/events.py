"""In-process, append-only event log (plan §2: "Kafka topic in production").

Sentinel consumes this; producers fire-and-forget. Deliberately trivial for the
hackathon — a module-level singleton list wrapped in a tiny class.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models import AgentEvent


class EventLog:
    def __init__(self) -> None:
        self._events: list[AgentEvent] = []

    def emit(self, *, session_id: str, agent: str, event_type: str, payload: dict | None = None) -> AgentEvent:
        event = AgentEvent(
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            agent=agent,
            event_type=event_type,
            payload=payload or {},
        )
        self._events.append(event)
        return event

    def all(self) -> list[AgentEvent]:
        return list(self._events)

    def of_type(self, event_type: str) -> list[AgentEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def clear(self) -> None:
        self._events.clear()


# Shared singleton used by agents. Sentinel will read `event_log.all()`.
event_log = EventLog()
