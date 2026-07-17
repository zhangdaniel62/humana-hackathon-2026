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
- session-based AHT, FCR, repeat-contact, escalation, ROI-gap, readiness, and
  corrective-intervention metrics
- adapters for the supplied synthetic claims and compliance CSV files
- application-scoped FastAPI lifecycle and read-only operational APIs
- Streamlit renderer plus the dependency-free `/operations` dashboard
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

`main.py` creates one shared event log and Sentinel instance, starts the
consumer in the composed FastAPI lifespan, and stops it during shutdown. For a
standalone application, the equivalent setup is:

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
- `network_gap_detected`
- `denial_risk_detected`
- `intervention_recommended`
- `intervention_recorded`
- `escalation_triggered`

Every event needs a `session_id`, `agent`, `event_type`, and timestamp. Include
`member_id` and `claim_id` whenever they apply. A `session_completed` payload
should include `duration_seconds`, `resolved`, `repeat_contact`,
and `human_escalation` so the dashboard metrics are computed rather than
hardcoded. Readiness and intervention events must carry the same claim and
member IDs plus `rule_id`, exact `evidence`, `recommended_action`,
`event_source`, and the synthetic label.

## Metric formulas

- **AHT:** mean `duration_seconds / 60` over the latest completion event for
  each completed session.
- **FCR:** completed sessions marked `first_contact_resolution`, defaulting to
  resolved with no repeat contact and no human escalation, divided by completed
  sessions.
- **Repeat-contact rate:** completed sessions marked `repeat_contact` divided
  by completed sessions.
- **Escalation rate:** completed sessions marked `human_escalation` divided by
  completed sessions.
- **ROI-gap rate:** unique ROI-gap sessions divided by unique observed
  `session_started` sessions.
- **At-risk claims identified:** unique claim IDs with a reviewed
  `denial_risk_detected` event.
- **Corrective interventions recorded:** unique claim IDs present in the
  intersection of `denial_risk_detected`, `intervention_recommended`, and
  `intervention_recorded` events. This is not a claim that a denial was
  prevented.

The dashboard baseline is explicitly labeled `synthetic_demo_assumption`; it is
not historical Humana performance.

All included data is synthetic. Never add real PHI.

## Persisted synthetic dashboard history

Sentinel's `/api/metrics` projection remains the in-process view of live demo
events. For multiweek charts, the manager-only
`/api/operations/dashboard` endpoint reads deterministic synthetic history from
the same local SQLite file used by authentication. Initialize it with:

```shell
uv run python -m src.operations.bootstrap
```

The persisted history is explicitly labeled `synthetic_demo`. Its call rows use
only claim/member pairs already present in the immutable claims snapshot; it
does not add or update claims, members, or adjudication outcomes. AHT is computed
over calls in the selected range. FCR and repeat-contact rates use mature
initial-contact cohorts with a seven-day observation window, and follow-up
searches may extend beyond the reporting end date. The intervention funnel ends
at a recorded corrective action and must be labeled intervention coverage, not
denials prevented.
