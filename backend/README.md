# Claim Story backend

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

## Integrated P1 demo and APIs

Start the backend, then open `http://localhost:8000/operations`. The page can
run the fixed, offline-safe golden path and trace its metrics and alerts back to
event IDs. The original caller fallback remains at `/demo/`.

```shell
uv run uvicorn main:app --reload
```

Operational endpoints:

- `GET /api/events`
- `GET /api/alerts`
- `GET /api/metrics`
- `GET /api/sessions/{session_id}/summary`
- `POST /api/demo/golden-path` (synthetic local demo trigger)

The golden path uses member `MBR00109`, denied claim `CLM000490`, and In Review
claim `CLM000493`. Its notification is always a grounded `preview` with
delivery status `not_sent`; no external message is delivered.
