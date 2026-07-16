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

Run the offline test suite from this directory:

```shell
uv run python -m unittest discover -s tests -v
```

Live checks are opt-in:

```shell
RUN_BIGQUERY_INTEGRATION=1 uv run python -m unittest tests.test_claim_story_integration -v
RUN_VERTEX_INTEGRATION=1 uv run python -m unittest tests.test_claim_story_integration -v
```
