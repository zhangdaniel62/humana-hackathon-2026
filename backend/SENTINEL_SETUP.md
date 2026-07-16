# Sentinel Agent setup

The Sentinel is an asynchronous event consumer. It never blocks a caller
request. Other agents publish structured `AgentEvent` objects to the shared
`EventLog`, and Sentinel turns those events into explainable operational and
compliance alerts.

## What is included

- append-only, in-process event log with asynchronous subscribers
- denial spike detection
- ROI authorization-gap frequency detection
- repeat-contact detection for the same member and claim
- compliance and escalation alerts
- session-based AHT, FCR, repeat-contact, escalation, and prevention metrics
- adapters for the supplied synthetic claims and compliance CSV files
- Streamlit dashboard rendering function
- focused tests and a historical-data replay demo

## Setup

Run these commands from `backend/`:

```shell
uv sync --dev
uv run pytest -q
uv run python sentinel_demo.py
```

The replay demo reads the repository's `datasets/` directory by default. Pass
`--datasets` to use a different directory and `--output` to write the snapshot
as JSON.

## Runtime integration

Create one event log and Sentinel instance during application startup:

```python
from src.agents import SentinelAgent
from src.events import EventLog

event_log = EventLog()
sentinel = SentinelAgent(event_log)
await sentinel.start()
```

Publish events from specialist agents without waiting for Sentinel:

```python
from src.models import AgentEvent, EventType

event_log.publish_nowait(
    AgentEvent(
        session_id=context.session_id,
        agent="claim_story",
        event_type=EventType.DENIAL_EXPLAINED,
        member_id=context.subject_member_id,
        claim_id=claim.id,
        payload={
            "denial_code": denial.code,
            "cause_category": denial.cause_category,
        },
    )
)
```

Use `sentinel.snapshot()` for dashboard data and call `await sentinel.stop()`
during application shutdown.

## Events expected from the team

- `session_started`
- `session_completed`
- `denial_explained`
- `roi_gap_detected`
- `coverage_question_answered`
- `escalation_triggered`

Every event needs a `session_id`, `agent`, `event_type`, and timestamp. Include
`member_id` and `claim_id` whenever they apply. A `session_completed` payload
should include `duration_seconds`, `resolved`, `repeat_contact`,
`human_escalation`, and `preventable_denial_caught` so the dashboard metrics are
computed rather than hardcoded.

All included data is synthetic. Never add real PHI.
