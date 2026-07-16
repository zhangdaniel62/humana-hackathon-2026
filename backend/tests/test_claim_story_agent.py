"""Tests for the Google ADK claim-story agent factory."""

from __future__ import annotations

import unittest

from google.adk.tools import FunctionTool

from src.agents.claim_story import (
    CLAIM_STORY_OUTPUT_KEY,
    CLAIM_STORY_STATE_KEY,
    create_claim_story_agent,
)
from src.models.claims import ClaimStoryRequest, ClaimStoryResult
from src.settings import Settings


class EmptyRepository:
    def get_claim(self, claim_id: str):
        return None


class FakeToolContext:
    def __init__(self) -> None:
        self.state: dict = {}


def build_test_settings() -> Settings:
    return Settings(
        _env_file=None,
        google_cloud_project="test-project",
        google_cloud_location="us-central1",
        google_genai_use_vertexai=True,
        model_name="gemini-test",
        bigquery_dataset="test_dataset",
        bigquery_location="US",
        gcs_bucket="test-bucket",
    )


class ClaimStoryAgentTests(unittest.TestCase):
    def test_factory_configures_structured_agent_tool_compatible_agent(self) -> None:
        agent = create_claim_story_agent(build_test_settings(), EmptyRepository())

        self.assertEqual("claim_story_agent", agent.name)
        self.assertEqual("gemini-test", agent.model)
        self.assertIs(ClaimStoryRequest, agent.input_schema)
        self.assertIs(ClaimStoryResult, agent.output_schema)
        self.assertEqual(CLAIM_STORY_OUTPUT_KEY, agent.output_key)
        self.assertEqual("chat", agent.mode)
        self.assertEqual("none", agent.include_contents)
        self.assertEqual(0.1, agent.generate_content_config.temperature)
        self.assertEqual(1, len(agent.tools))
        self.assertIsInstance(agent.tools[0], FunctionTool)

    def test_lookup_tool_stores_namespaced_state(self) -> None:
        agent = create_claim_story_agent(build_test_settings(), EmptyRepository())
        tool = agent.tools[0]
        context = FakeToolContext()

        payload = tool.func(" clm999999 ", context)

        self.assertEqual("not_found", payload["status"])
        self.assertEqual(payload, context.state[CLAIM_STORY_STATE_KEY])

    def test_agent_can_be_wrapped_as_an_agent_tool(self) -> None:
        from google.adk.tools.agent_tool import AgentTool

        agent = create_claim_story_agent(build_test_settings(), EmptyRepository())
        tool = AgentTool(agent)

        self.assertEqual("claim_story_agent", tool.name)


if __name__ == "__main__":
    unittest.main()
