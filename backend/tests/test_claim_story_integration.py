"""Opt-in tests against live BigQuery and Vertex AI resources."""

from __future__ import annotations

import os
import unittest

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from src.agents.claim_story import create_claim_story_agent
from src.clients.claims import BigQueryClaimsRepository
from src.models.claims import ClaimStoryResult
from src.settings import settings


@unittest.skipUnless(
    os.environ.get("RUN_BIGQUERY_INTEGRATION") == "1",
    "set RUN_BIGQUERY_INTEGRATION=1 to query live BigQuery",
)
class BigQueryIntegrationTests(unittest.TestCase):
    def test_known_live_claim(self) -> None:
        claim = BigQueryClaimsRepository(settings).get_claim("CLM000001")

        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual("CLM000001", claim.claim_id)


@unittest.skipUnless(
    os.environ.get("RUN_VERTEX_INTEGRATION") == "1",
    "set RUN_VERTEX_INTEGRATION=1 to invoke the configured Vertex AI model",
)
class VertexAgentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_returns_structured_output(self) -> None:
        session_service = InMemorySessionService()
        claim_story_agent = create_claim_story_agent(settings)
        agent = LlmAgent(
            name="claim_story_integration_root",
            model=settings.model_name,
            instruction=(
                "Call claim_story_agent exactly once for the supplied claim ID. "
                "Return its result without changing any facts."
            ),
            tools=[AgentTool(claim_story_agent)],
            mode="chat",
        )
        runner = Runner(
            app_name="claim_story_integration",
            agent=agent,
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="claim_story_integration",
            user_id="integration-test",
        )
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text='{"claim_id":"CLM000001"}')],
        )

        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            pass

        updated = await session_service.get_session(
            app_name="claim_story_integration",
            user_id=session.user_id,
            session_id=session.id,
        )
        assert updated is not None
        ClaimStoryResult.model_validate(updated.state["claim_story.result"])
        await runner.close()


if __name__ == "__main__":
    unittest.main()
