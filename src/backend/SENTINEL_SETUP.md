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

## Windows setup without uv

Run these commands from `src\backend` in PowerShell. They do not require
activating the virtual environment.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-sentinel.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe sentinel_demo.py --datasets ..\..\datasets
```

If `py -3.12` is unavailable but `python --version` reports Python 3.12 or
newer, replace `py -3.12` in the first command with `python`.

## Runtime integration

Create one event log and Sentinel instance during application startup:

```python
event_log = EventLog()
sentinel = SentinelAgent(event_log)
await sentinel.start()
```

Publish events from specialist agents without waiting for Sentinel:

```python
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
