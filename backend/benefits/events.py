"""In-process event log. Fire-and-forget; never in the request path.

A list is the whole implementation for the hackathon ("a Kafka topic in
production"). Sentinel consumes these. Swap `emit` for a real producer without
touching any caller.
"""

from datetime import UTC, datetime
from typing import Any

EVENT_LOG: list[dict[str, Any]] = []


def emit(event_type: str, payload: dict[str, Any], *, agent: str = "benefits_qa") -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": agent,
        "event_type": event_type,
        **payload,
    }
    EVENT_LOG.append(event)
    return event


def drain() -> list[dict[str, Any]]:
    events, EVENT_LOG[:] = list(EVENT_LOG), []
    return events
