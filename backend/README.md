# Claim Assist backend

FastAPI and Google ADK backend for Claim Assist. It provides authenticated
Chat/Voice conversations, grounded claim and benefit guidance, deterministic
ROI and claim-readiness controls, Sentinel monitoring, and the manager
operations APIs used by the React frontend. The Claim Story capability below is
one of the specialized backend services.

For the product overview, screenshots, and full-stack quick start, see the
[repository README](../README.md).

## Claim Story capability

The claim-story subagent reads one exact claim from BigQuery, validates it with
Pydantic, prepares deterministic lifecycle and denial facts, and uses Google ADK
for a structured member-friendly response.

The public factory is:

```python
from src.agents.claim_story import create_claim_story_agent

agent = create_claim_story_agent()
```

The returned `LlmAgent` accepts `{"claim_id": "CLM000001"}` and can be wrapped
with ADK's `AgentTool` by the future orchestrator.

Run the offline test suite from this directory (the two required cloud settings
may be harmless placeholders for deterministic tests when no `.env` is present):

```shell
GOOGLE_CLOUD_PROJECT=test-project GCS_BUCKET=test-bucket uv run pytest -q
```

Live checks are opt-in:

```shell
RUN_BIGQUERY_INTEGRATION=1 uv run python -m unittest tests.test_claim_story_integration -v
RUN_VERTEX_INTEGRATION=1 uv run python -m unittest tests.test_claim_story_integration -v
```

## Sentinel monitoring

Sentinel consumes structured backend events asynchronously and produces
explainable operational and compliance alerts plus session metrics. Its code
lives with the rest of the application under `src/`.

Run its historical-data replay from this directory:

```shell
uv run python sentinel_demo.py
```

See [SENTINEL_SETUP.md](SENTINEL_SETUP.md) for event contracts, configuration,
and dashboard integration.

## Integrated application and APIs

Start the backend, then start the React app from `frontend/` with `pnpm dev` and
open `http://127.0.0.1:5173`. Vite proxies `/api` and `/ws` to this backend so
the HTTP-only session cookie is shared by the authenticated REST and WebSocket
contracts. The original `/operations` and `/demo/` pages remain direct backend
validation surfaces.

```shell
uv run uvicorn main:app --reload
```

Operational endpoints:

- `GET /api/events`
- `GET /api/alerts`
- `GET /api/metrics`
- `GET /api/operations/dashboard?start=YYYY-MM-DD&end=YYYY-MM-DD&bucket=week`
- `GET /api/sessions/{session_id}/summary`
- `POST /api/demo/golden-path` (synthetic local demo trigger)
- `POST /api/prevention/scans` (manager-only idempotent population scan)
- `GET /api/rep/work-items` (rep-only open plus assigned queue)
- `POST /api/rep/work-items/{id}/claim|resolve|dismiss`
- `GET /api/delegation/traces` (manager-only trace metadata)
- `GET /api/runtime/readiness` (manager-only database/last-scan readiness)

After starting the backend, inspect the chart-ready dashboard response with the
development manager account:

```shell
curl -c /tmp/claim-assist-cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"manager","password":"ManagerDemo2026!"}' \
  http://localhost:8000/api/auth/login
curl -b /tmp/claim-assist-cookies.txt \
  'http://localhost:8000/api/operations/dashboard?bucket=week'
```

The caller conversation backend is available at `WS /ws/conversation`, with
`/ws/voice` retained as an alias. Customers and reps may enable Voice mode and
receive streaming user and agent transcripts. Agent audio is sent only to
Voice-mode sessions, and both customer and representative roles have audio
parity. The frontend may choose whether playback is appropriate for a
particular call-center setup. The connection starts in Chat mode and emits
`session_started` with a session ID, the session-summary URL,
`agent_audio_enabled`, and the 16 kHz input / 24 kHz output PCM formats. Text uses
`{"type":"text","text":"..."}`. The same session switches either direction
with `{"type":"set_mode","mode":"chat|voice"}`; binary PCM16 microphone and
spoken-response frames are enabled only in Voice mode when
`agent_audio_enabled` is true. Each `turn_complete` message includes the summary
URL for refreshing structured result cards.
Malformed typed messages and live-service failures return user-safe `error`
messages; backend exception details are never sent to the browser.

The golden path uses member `MBR00109`, denied claim `CLM000490`, and In Review
claim `CLM000493`. Its notification is always a grounded `preview` with
delivery status `not_sent`; no external message is delivered.

## Local authentication

The backend uses one local SQLite file for Argon2-backed users, server-side
sessions, and synthetic operations history. Create or refresh it from the
tracked schemas and deterministic development seeds:

```shell
uv run python -m src.operations.bootstrap
```

The generated `.data/auth.sqlite3` is not tracked. The supplied CSV/BigQuery
datasets are never copied, expanded, or modified. The operations seed adds only
new synthetic interaction facts whose claim/member pairs are validated against
`datasets/claims.csv`.

| Role | Username | Development-only password |
|---|---|---|
| Manager | `manager` | `ManagerDemo2026!` |
| Customer | `customer` | `CustomerDemo2026!` |
| Representative | `rep` | `RepDemo2026!` |
| Dashboard representative | `rep.alex` | `RepDemo2026!` |
| Dashboard representative | `rep.jordan` | `RepDemo2026!` |
| Dashboard representative | `rep.morgan` | `RepDemo2026!` |
| Dashboard representative | `rep.taylor` | `RepDemo2026!` |

These credentials are synthetic and must not be reused for real users. Set
`AUTH_ENABLE_DEMO_SEED=false` outside local or hackathon environments.

Auth endpoints:

- `POST /api/auth/login` with `{"username":"...","password":"..."}`
- `GET /api/auth/me`
- `POST /api/auth/logout`

The manager-only operations endpoint returns one chart-ready payload containing
the synthetic baseline, AHT/FCR/repeat trends, seven-day cohort denominators,
automated versus manual-review volume, per-rep manual workload, and the
claim-intervention funnel. Repeat contact and FCR are derived from separate call
rows; recent contacts remain immature until their seven-day follow-up window
closes. When dates are omitted, trend output stops at the latest completed week
or month while repeat detection can still inspect later follow-ups. Intervention
coverage is not presented as proof that a denial was prevented.

Managers use the live React operations dashboard and raw ADK developer APIs.
Customers use the React Chat/Voice page backed by `/ws/conversation` and their
owned session summaries. Representatives use the capability-protected synthetic
queue/workspace demo and may also connect to the conversation backend. Customer
and rep Voice sessions may stream microphone audio and receive transcripts and
spoken responses. The frontend uses the authenticated role, `capabilities`, and
`agent_audio_enabled` field to select its presentation.

## Evaluation and durable prototype boundary

Run the deterministic quality corpus and write JSON/Markdown reports:

```shell
uv run python -m src.evaluation.run
```

The offline run enforces category thresholds for grounding, reviewed readiness
rules, ROI, disclosure safety, and the declared routing contract. It does not
claim live-model routing accuracy. Run the credentialed ADK case explicitly:

```shell
uv run python -m src.evaluation.run --live
```

The shared SQLite file persists proactive work items, idempotency records,
metadata-only delegation traces, and structured Sentinel events. Startup runs
one idempotent synthetic scan and replays stored event IDs exactly once. ADK
live sessions and session-summary projections remain process-local.

Container startup uses the tracked Dockerfile. Run the build from the repository
root so the image includes the synthetic datasets required by startup seeding:

```shell
docker build -f backend/Dockerfile -t claim-assist-backend .
docker run --rm -p 8000:8000 --env-file .env claim-assist-backend
```

For local testing without a login cookie, enable the explicit development-only
auth bypass in `.env` and restart the server:

```dotenv
AUTH_BYPASS_ENABLED=true
AUTH_BYPASS_ROLE=customer
```

Use `customer` or `rep` to test spoken AI output in Voice mode.
The bypass still enforces allowed browser origins and the selected role's
permissions. It is disabled by default and must never be enabled in a deployed
environment.
