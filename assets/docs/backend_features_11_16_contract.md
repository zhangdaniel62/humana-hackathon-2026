# Backend Features 11–16 contract

This document is the implementation handoff for the backend work added after
the original P1 checkpoint. `overall_plan.md` remains the product source of
truth; this file records the concrete API/runtime contract.

## Feature 11 — Expanded golden path

`POST /api/demo/golden-path` is manager-only. The optional body is:

```json
{"idempotency_key": "golden-path-v2"}
```

The result is labeled `workflow_mode: synthetic_rep_simulation` and includes
the original grounded ROI/claim/benefit/readiness/preview/intervention fields,
plus `prevention_scan`, a resolved `rep_work_item`, an explicitly offline
fallback `delegation_trace`, and the offline `evaluation` summary. Reusing an
idempotency key returns `replayed: true` without publishing new events or
changing metrics.

## Feature 12/15 — Rep queue and Voice parity

Customer and rep WebSockets both announce `agent_audio_enabled: true` when the
role has the Voice capability. Audio bytes are still sent only while the
connection is in Voice mode.

Queue endpoints require `rep_queue`; the scanner requires manager role:

- `POST /api/prevention/scans`
- `GET /api/rep/work-items?limit=100`
- `POST /api/rep/work-items/{id}/claim`
- `POST /api/rep/work-items/{id}/resolve`
- `POST /api/rep/work-items/{id}/dismiss`

A scan body contains `idempotency_key` and an optional `limit`. Transition
bodies contain `expected_version`. A work item exposes only claim/rule/action,
priority, state, assignment username, version, and timestamps. It never exposes
member data, transcripts, session summaries, raw claim rows, or manager metrics.

The legal state flow is `open -> claimed -> resolved|dismissed`. Claiming is an
atomic open/version comparison. Only the assigned rep can make a terminal
transition. Missing items return `404`; stale versions, assignment conflicts,
and illegal transitions return `409`.

## Feature 13 — Evaluation

Run the offline CI suite from `backend/`:

```shell
uv run python -m src.evaluation.run
```

Reports are written to `artifacts/evaluation/latest.json` and `latest.md`. The
command exits nonzero if overall or any category falls below the configured
pass rate. Offline latency is reported but not gated. The `routing_contract`
category is a transparent deterministic contract check, not live-model
accuracy. `--live` opts into one credentialed Vertex/ADK typed Claim Story run.

## Feature 14 — Delegation trace

The root's `lookup_claim_story` tool is a real ADK `AgentTool`. The specialist
result must validate as `ClaimStoryResult` and match the deterministic claim ID,
member ID, status, amounts, and grounding reference. Otherwise the tool returns
the existing server-enforced deterministic result.

`GET /api/delegation/traces` is manager-only. Trace rows contain only trace,
session/work-item correlation, specialist, timestamps, latency, outcome, and an
exception class. They do not persist prompts, utterances, tool arguments,
member facts, or full outputs.

## Feature 16 — Runtime boundary

SQLite persists users/sessions, dashboard history, prevention work, scan and
golden-path idempotency, trace metadata, and operational events. On startup the
application attaches the event store, replays stored event IDs into Sentinel,
and runs one idempotent synthetic population scan. Tests verify restart replay
and duplicate suppression.

- `GET /health` is public liveness.
- `GET /api/runtime/readiness` is manager-only and returns database state plus
  the last completed scan without paths or secrets.
- `backend/Dockerfile` starts one Uvicorn worker and checks `/health`.

ADK live sessions and session-summary projections are still in process. There
is no distributed scheduler, leader election, managed database, Kafka, or
enterprise retention claim.
