"""Tests for the voice orchestrator agent factory."""

from __future__ import annotations

import unittest

from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool

from src.agents.claim_story import CLAIM_STORY_STATE_KEY
from src.agents.orchestrator import create_voice_orchestrator
from src.clients.member_records import Authorization, FakeMemberRecordsClient
from src.settings import Settings
from tests.claim_fixtures import load_claim_rows


class EmptyRepository:
    def get_claim(self, claim_id: str):
        return None


class StaticRepository:
    def __init__(self, claim_ids: set[str]) -> None:
        self.claims = {
            claim.claim_id: claim
            for claim in load_claim_rows()
            if claim.claim_id in claim_ids
        }

    def get_claim(self, claim_id: str):
        return self.claims.get(claim_id)


class FakeToolContext:
    def __init__(self, **state) -> None:
        self.state: dict = state


def fake_member_records() -> FakeMemberRecordsClient:
    return FakeMemberRecordsClient(
        [
            Authorization(
                "AUTH1",
                "MBR00183",
                "Natalie Chang",
                "Self representative",
                True,
                "2099-12-31",
                False,
            )
        ]
    )


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
        agent = create_voice_orchestrator(
            build_test_settings(),
            EmptyRepository(),
            member_records_client=fake_member_records(),
        )

        self.assertEqual("voice_orchestrator", agent.name)
        self.assertEqual("gemini-live-test", agent.model.model)
        self.assertEqual(
            "us-central1", agent.model.client_kwargs["location"]
        )
        self.assertEqual("chat", agent.mode)
        self.assertEqual(6, len(agent.tools))
        self.assertIsInstance(agent.tools[0], FunctionTool)
        self.assertIsInstance(agent.tools[1], AgentTool)
        self.assertTrue(
            all(isinstance(tool, FunctionTool) for tool in agent.tools[2:])
        )
        self.assertEqual(
            [
                "establish_member_context",
                "lookup_claim_story",
                "screen_claim_readiness",
                "record_corrective_intervention",
                "lookup_coverage",
                "find_provider",
            ],
            [tool.name for tool in agent.tools],
        )

    def test_model_override_for_text_channels(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            EmptyRepository(),
            model_name="gemini-test",
            member_records_client=fake_member_records(),
        )

        self.assertEqual("gemini-test", agent.model)

    def test_lookup_tool_is_grounded_in_repository(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            EmptyRepository(),
            member_records_client=fake_member_records(),
        )
        context = FakeToolContext(caller_id="MBR00183")
        tools = {tool.name: tool for tool in agent.tools}
        tools["establish_member_context"].func(
            "Natalie Chang", "MBR00183", context
        )

        payload = tools["lookup_claim_story"].func("CLM999999", context)

        self.assertEqual("not_found", payload["status"])
        self.assertEqual(payload, context.state[CLAIM_STORY_STATE_KEY])

    def test_instruction_forbids_invented_claim_facts(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            EmptyRepository(),
            member_records_client=fake_member_records(),
        )

        self.assertIn("Never invent claim facts", agent.instruction)
        self.assertIn("lookup_claim_story", agent.instruction)
        self.assertIn("screen_claim_readiness", agent.instruction)
        self.assertIn("lookup_coverage", agent.instruction)
        self.assertIn("establish_member_context", agent.instruction)
        self.assertIn("two-turn confirmation gate", agent.instruction)
        self.assertIn("do not call the", agent.instruction)
        self.assertIn("claim tool in that turn", agent.instruction)

    def test_one_context_can_support_claim_then_benefit_intents(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            EmptyRepository(),
            member_records_client=fake_member_records(),
        )
        tools = {tool.name: tool for tool in agent.tools}
        context = FakeToolContext()

        roi = tools["establish_member_context"].func(
            "Natalie Chang", "MBR00183", context
        )
        claim = tools["lookup_claim_story"].func("CLM999999", context)
        benefit = tools["lookup_coverage"].func("colonoscopy", context)

        self.assertEqual("verified", roi["roi"]["status"])
        self.assertEqual("not_found", claim["status"])
        self.assertEqual("ok", benefit["status"])
        self.assertEqual("MBR00183", context.state["subject_member_id"])
        self.assertEqual("verified", context.state["roi_status"])

    def test_one_context_preserves_claim_benefit_and_readiness_findings(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            StaticRepository({"CLM000377", "CLM000378"}),
            member_records_client=fake_member_records(),
        )
        tools = {tool.name: tool for tool in agent.tools}
        context = FakeToolContext(caller_id="MBR00087")

        roi = tools["establish_member_context"].func(
            "Danielle Espinoza", "MBR00087", context, "English"
        )
        claim = tools["lookup_claim_story"].func("CLM000378", context)
        benefit = tools["lookup_coverage"].func("70553", context)
        readiness = tools["screen_claim_readiness"].func(
            "CLM000377", context
        )

        self.assertEqual("not_required", roi["roi"]["status"])
        self.assertEqual("success", claim["status"])
        self.assertEqual("ok", benefit["status"])
        self.assertEqual("high", readiness["assessment"]["risk_band"])
        self.assertEqual(
            {
                "roi_gatekeeper",
                "claim_story",
                "benefits_qa",
                "claim_readiness",
                "notification_preview",
            },
            set(context.state["agent_findings"]),
        )
        self.assertEqual(
            [
                "establish_member_context",
                "claim_story",
                "benefits_qa",
                "claim_readiness",
            ],
            context.state["intent_history"],
        )

    def test_claim_member_mismatch_discloses_no_claim_facts(self) -> None:
        agent = create_voice_orchestrator(
            build_test_settings(),
            StaticRepository({"CLM000804"}),
            member_records_client=fake_member_records(),
        )
        tools = {tool.name: tool for tool in agent.tools}
        context = FakeToolContext(caller_id="MBR00087")
        tools["establish_member_context"].func(
            "Danielle Espinoza", "MBR00087", context
        )

        payload = tools["lookup_claim_story"].func("CLM000804", context)

        self.assertEqual(
            {"status", "claim_id", "message"},
            set(payload),
        )
        self.assertEqual("member_mismatch", payload["status"])
        self.assertNotIn("MBR00183", str(payload))


if __name__ == "__main__":
    unittest.main()
