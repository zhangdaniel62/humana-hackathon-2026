# Claim Story AI — Project Context

Humana hackathon 2026. A multi-agent Member & Claims Intelligence system on Google's
Agent Development Kit (ADK / `google-adk`). Full spec: `assets/docs/initial_plan.md`
(read §5 data models, §6 Phase 2, note #4 ADK guidance, and note #5a before touching
the ROI agent).

The system routes caller interactions through an orchestrator to specialist agents that
share one session context. This file is the working context for building agents; keep it
current as pieces land.

## Stack (verified installed — do not guess)
- Python 3.14, package manager `uv`. Run everything with `uv run ...` from `backend/`.
- `google-adk` **2.4.0**, `google-cloud-bigquery`, `pydantic` v2, `pydantic-settings`.
- **LLM: Gemini via Vertex AI** (NOT an API key). Config lives in `backend/.env`
  (template: `backend/.env.example`) and is loaded by `src/settings.py`:
  `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
  `MODEL_NAME` (default `gemini-3.5-flash`). Auth is via gcloud ADC (already available
  in this environment). There is NO `GOOGLE_API_KEY` in this project.
- **Data source: BigQuery** dataset `humana_hackathon`. The CSVs in `datasets/` are only
  the schema reference (table = CSV file name); real code queries BigQuery.

## Verified google-adk 2.4.0 API (introspected, not guessed)
```python
from google.adk.agents import LlmAgent            # name, description, model, instruction, tools, output_key, ...
from google.adk.runners import Runner             # Runner(app_name=, agent=, session_service=)
from google.adk.sessions import InMemorySessionService  # .create_session_sync(app_name, user_id, state, session_id)
from google.adk.tools import ToolContext          # tool fns can take tool_context: ToolContext; has .state (dict)
from google.genai import types                    # types.Content(role="user", parts=[types.Part(text=...)])
```
- A tool is a plain Python function; ADK reads its type hints + docstring. A
  `tool_context` param is injected by ADK and hidden from the LLM.
- Write shared state to `tool_context.state[...]` — ADK's native shared "whiteboard"
  downstream agents read. Do NOT hand-thread a custom context object (plan note #4).
- `Runner.run(user_id=, session_id=, new_message=)` yields events; final text is on
  events where `event.author == agent.name` and `event.content.parts[*].text`.
- ADK reads Vertex config from `os.environ`, not from pydantic Settings — bridge the
  values in (see `demo_roi.py::_bridge_settings_into_env`).

## Key gotcha: Settings() requires a real .env
`src/settings.py` declares `google_cloud_project` and `gcs_bucket` as REQUIRED, and does
`settings = Settings()` at import time. So importing that module fails until `backend/.env`
exists. Therefore: import `settings` **lazily inside functions**, never at module top, so
modules and unit tests stay importable without a `.env`.

## Core design constraints (non-negotiable — plan §8)
- **The LLM never decides facts.** Authorization, denial causes, coverage rules, resolution
  times all come from data/deterministic code. The LLM only narrates and handles intent.
- All external data sits behind client Protocols; the BigQuery impl is swappable.
- Agents fire-and-forget structured events to an in-process append-only `EventLog`
  ("Kafka topic in production"). Sentinel consumes it; it is never in the request path.

## Repo layout (relevant parts)
```
datasets/                       # CSV schema reference for the BigQuery tables
backend/
  .env.example / .env           # Vertex + BigQuery config
  pyproject.toml
  src/
    settings.py                 # pydantic-settings Settings (source of truth for config)
    models.py                   # Pydantic: ROIStatus, ROICheckResult, AgentEvent
    events.py                   # EventLog (append-only)
    clients/member_records.py   # MemberRecordsClient protocol + BigQuery + Fake impls
    agents/roi_gatekeeper.py    # deterministic check + ADK LlmAgent
  tests/test_roi_check.py       # pure-logic tests via FakeMemberRecordsClient (no creds)
  demo_roi.py                   # deterministic demo + --live (BigQuery+Vertex) demo
assets/docs/initial_plan.md     # full spec
```
Imports are package-style from the `backend/` root: `from src.agents.roi_gatekeeper import ...`.

## ROI Gatekeeper Agent (agent #3) — BUILT
Pre-screens a session: is the *caller* allowed to discuss the *subject member*'s info?
Writes `roi_status` into session state; downstream agents limit detail when it's `missing`.

**Gating is conditional (plan note #5a):** only gate when the caller is NOT the member.

**Status values:**
- `not_required` — caller is the subject member.
- `verified` — a matching authorization row is on file, not expired, not past expiration.
- `missing` — no valid authorization (none/name-not-found/expired/unknown member). Returns
  the self-service ROI-submission path and emits a `roi_gap_detected` event.

Layers: `check_roi_authorization()` is pure/deterministic and decides the status (tested
with a fake client, no creds); `build_roi_agent()` is a thin `LlmAgent` that calls the
`roi_gate` tool and narrates. Data via `BigQueryMemberRecordsClient` in production.

### BigQuery table — `roi_authorizations` (columns from datasets/roi_authorizations.csv)
`auth_id, member_id, authorized_caller_name, relationship, auth_on_file, expiration_date,
auth_expired, date_added`. A member can have MULTIPLE authorized callers. `verified` =
`auth_on_file=true` AND `auth_expired=false` AND `expiration_date >= today`.

### BigQuery table — `members` (columns from datasets/members.csv)
Key: `member_id, first_name, last_name, dob, plan_type, plan_id`. Caller counts as "self"
when their name matches the subject member's `first_name last_name`.

### Other tables (owned by OTHER agents — ignore for ROI work)
`claims, coverage_rules, care_gaps, compliance_flags, providers, stars_performance,
historical_interventions, segment_performance, campaign_dispositions, appointment_slots`.

## How to run (from backend/)
```bash
uv sync
uv run python -m pytest tests/ -q     # deterministic logic — no .env/BigQuery needed
uv run python demo_roi.py             # offline demo (fake data mirroring BigQuery rows)

cp .env.example .env                  # then fill GOOGLE_CLOUD_PROJECT + GCS_BUCKET
uv run python demo_roi.py --live      # real: BigQuery data + Gemini via Vertex
```
