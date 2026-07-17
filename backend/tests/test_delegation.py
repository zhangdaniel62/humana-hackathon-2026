"""Runner-level proof of the typed ADK specialist handoff and safe fallback."""

from __future__ import annotations

import asyncio

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import PrivateAttr

from src.agents.claim_story import (
    CLAIM_STORY_STATE_KEY,
    build_lookup_claim_story_tool,
    create_claim_story_agent,
)
from src.agents.delegation import TracedClaimStoryAgentTool
from src.delegation import DelegationTraceStore, InMemoryDelegationTraceStore
from src.models import DelegationTrace
from datetime import UTC, datetime
from src.services.claim_story import ClaimStoryService
from src.settings import Settings
from tests.claim_fixtures import claim_for_status
from src.models import ClaimStatus


class StaticRepository:
    def __init__(self, claim):
        self.claim = claim

    def get_claim(self, claim_id):
        return self.claim if claim_id == self.claim.claim_id else None


class RootRoutingModel(BaseLlm):
    _calls: int = PrivateAttr(default=0)

    async def generate_content_async(self, llm_request, stream=False):
        self._calls += 1
        if self._calls == 1:
            part = types.Part.from_function_call(
                name="lookup_claim_story",
                args={"claim_id": "CLM200001"},
            )
        else:
            part = types.Part.from_text(text="Grounded specialist result received.")
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


class SpecialistModel(BaseLlm):
    _calls: int = PrivateAttr(default=0)
    _payload: str = PrivateAttr()

    def __init__(self, *, payload: str):
        super().__init__(model="specialist-test")
        self._payload = payload

    async def generate_content_async(self, llm_request, stream=False):
        self._calls += 1
        if self._calls == 1:
            part = types.Part.from_function_call(
                name="lookup_claim_story",
                args={"claim_id": "CLM200001"},
            )
        else:
            part = types.Part.from_text(text=self._payload)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


class BrokenSpecialistModel(BaseLlm):
    async def generate_content_async(self, llm_request, stream=False):
        raise RuntimeError("synthetic specialist failure")
        yield


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        google_cloud_project="test-project",
        gcs_bucket="test-bucket",
        model_name="model-test",
    )


async def _run_with_specialist(model: BaseLlm):
    claim = claim_for_status(ClaimStatus.DENIED).model_copy(
        update={"claim_id": "CLM200001"}
    )
    repository = StaticRepository(claim)
    service = ClaimStoryService(repository)
    fallback = build_lookup_claim_story_tool(
        service, enforce_member_context=True
    )
    specialist = create_claim_story_agent(
        _settings(),
        repository,
        model=model,
        agent_name="lookup_claim_story",
        enforce_member_context=True,
    )
    traces = InMemoryDelegationTraceStore()
    tool = TracedClaimStoryAgentTool(
        agent=specialist,
        fallback_tool=fallback,
        service=service,
        trace_sink=traces,
    )
    root = LlmAgent(
        name="delegation_test_root",
        model=RootRoutingModel(model="root-test"),
        instruction="Delegate the exact claim ID to lookup_claim_story.",
        tools=[tool],
        mode="chat",
    )
    sessions = InMemorySessionService()
    runner = Runner(
        app_name="delegation_test",
        agent=root,
        session_service=sessions,
    )
    session = await sessions.create_session(
        app_name="delegation_test",
        user_id="rep-1",
        state={
            "session_id": "session-1",
            "subject_member_id": claim.member_id,
            "roi_status": "not_required",
        },
    )
    message = types.Content(
        role="user", parts=[types.Part.from_text(text=claim.claim_id)]
    )
    async for _ in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=message,
    ):
        pass
    updated = await sessions.get_session(
        app_name="delegation_test",
        user_id=session.user_id,
        session_id=session.id,
    )
    await runner.close()
    assert updated is not None
    return updated, traces


def test_runner_invokes_real_typed_specialist_agent() -> None:
    canonical = ClaimStoryService(
        StaticRepository(
            claim_for_status(ClaimStatus.DENIED).model_copy(
                update={"claim_id": "CLM200001"}
            )
        )
    ).prepare("CLM200001")
    specialist_model = SpecialistModel(payload=canonical.model_dump_json())

    updated, traces = asyncio.run(_run_with_specialist(specialist_model))

    assert specialist_model._calls == 2
    assert updated.state[CLAIM_STORY_STATE_KEY]["status"] == "success"
    assert traces.traces[0].outcome == "success"
    assert traces.traces[0].session_id == "session-1"
    assert set(traces.traces[0].model_dump()) == {
        "trace_id",
        "session_id",
        "work_item_id",
        "specialist",
        "started_at",
        "completed_at",
        "latency_ms",
        "outcome",
        "error_code",
    }


def test_runner_falls_back_when_specialist_fails() -> None:
    updated, traces = asyncio.run(
        _run_with_specialist(BrokenSpecialistModel(model="broken-test"))
    )

    assert updated.state[CLAIM_STORY_STATE_KEY]["status"] == "success"
    assert traces.traces[0].outcome == "fallback"
    assert traces.traces[0].error_code == "RuntimeError"


def test_trace_metadata_survives_store_reopen_without_payloads(tmp_path) -> None:
    store = DelegationTraceStore(tmp_path / "traces.sqlite3")
    store.initialize()
    now = datetime.now(UTC)
    trace = DelegationTrace(
        trace_id="trace-1",
        session_id="session-1",
        work_item_id="work-1",
        specialist="claim_story_agent",
        started_at=now,
        completed_at=now,
        latency_ms=1.25,
        outcome="success",
    )
    store.record(trace)

    reloaded = DelegationTraceStore(store.database_path).list()

    assert len(reloaded) == 1
    assert reloaded[0].trace_id == "trace-1"
    assert set(reloaded[0].model_dump()) == {
        "trace_id",
        "session_id",
        "work_item_id",
        "specialist",
        "started_at",
        "completed_at",
        "latency_ms",
        "outcome",
        "error_code",
    }
