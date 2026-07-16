"""Tests for the voice orchestrator agent factory."""

from __future__ import annotations

import unittest

from google.adk.tools import FunctionTool

from src.agents.claim_story import CLAIM_STORY_STATE_KEY
from src.agents.orchestrator import create_voice_orchestrator
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
        live_model_name="gemini-live-test",
        live_voice_name="Aoede",
        bigquery_dataset="test_dataset",
        bigquery_location="US",
        gcs_bucket="test-bucket",
    )


class VoiceOrchestratorTests(unittest.TestCase):
    def test_factory_wires_live_model_and_lookup_tool(self) -> None:
        agent = create_voice_orchestrator(build_test_settings(), EmptyRepository())

        self.assertEqual("voice_orchestrator", agent.name)
        self.assertEqual("gemini-live-test", agent.model.model)
        self.assertEqual(
            "us-central1", agent.model.client_kwargs["location"]
        )
        self.assertEqual("chat", agent.mode)
        self.assertEqual(1, len(agent.tools))
        self.assertIsInstance(agent.tools[0], FunctionTool)
        self.assertEqual("lookup_claim_story", agent.tools[0].name)

    def test_model_override_for_text_channels(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(), EmptyRepository(), model_name="gemini-test"
        )

        self.assertEqual("gemini-test", agent.model)

    def test_lookup_tool_is_grounded_in_repository(self) -> None:
        agent = create_voice_orchestrator(build_test_settings(), EmptyRepository())
        context = FakeToolContext()

        payload = agent.tools[0].func("CLM999999", context)

        self.assertEqual("not_found", payload["status"])
        self.assertEqual(payload, context.state[CLAIM_STORY_STATE_KEY])

    def test_instruction_forbids_invented_claim_facts(self) -> None:
        agent = create_voice_orchestrator(build_test_settings(), EmptyRepository())

        self.assertIn("Never invent claim facts", agent.instruction)
        self.assertIn("lookup_claim_story", agent.instruction)


if __name__ == "__main__":
    unittest.main()
