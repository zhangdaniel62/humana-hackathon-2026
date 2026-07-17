"""Shared ADK root agent for live voice and typed Claim Assist channels."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import BaseTool, FunctionTool, ToolContext

from ..clients.claims import ClaimsRepository, create_claims_repository
from ..delegation.store import InMemoryDelegationTraceStore, TraceSink
from ..clients.member_records import (
    MemberRecordsClient,
    create_member_records_client,
)
from ..events import EventLog, event_log
from ..services.claim_readiness import ClaimReadinessService
from ..services.claim_story import ClaimStoryService
from ..settings import Settings, settings as default_settings
from .benefits import find_provider_tool, lookup_coverage
from .claim_readiness import (
    build_record_corrective_intervention_tool,
    build_screen_claim_readiness_tool,
)
from .claim_story import build_lookup_claim_story_tool
from .claim_story import create_claim_story_agent
from .delegation import TracedClaimStoryAgentTool
from .session_context import build_establish_member_context_tool

# Uvicorn's error logger is the server's configured console channel. A child
# logger keeps these messages visible at INFO without adding an extra handler
# that could duplicate them in tests or other hosts.
logger = logging.getLogger("uvicorn.error.claim_assist.routing")

ROUTED_AGENT_BY_TOOL = {
    "establish_member_context": "roi_gatekeeper",
    "lookup_claim_story": "claim_story_agent",
    "screen_claim_readiness": "claim_readiness_agent",
    "record_corrective_intervention": "claim_readiness_agent",
    "lookup_coverage": "benefits_agent",
    "find_provider": "benefits_agent",
}

VOICE_ORCHESTRATOR_INSTRUCTION = """
You are the Claim Assist agent for a health-plan member-services prototype.
The caller may use live voice or typed input. All records are synthetic demo
data.

Conversation rules:
- Greet the caller briefly and ask how you can help.
- Before any member-specific lookup, collect the caller's full name and the
  subject member ID, then call establish_member_context. Reuse that shared
  context across later turns, including caller, member, ROI, language, intent
  history, and structured findings.
- If establish_member_context returns missing, expired, or unknown ROI, do not
  call any member-specific claim, readiness, benefit, or provider tool. Explain
  the approved next step from the result.
- Claim IDs use a strict two-turn confirmation gate. When the caller first
  supplies an exact claim ID for Claim Story or Claim Readiness, do not call the
  claim tool in that turn. Repeat the ID and ask the caller to confirm it.
- Call lookup_claim_story or screen_claim_readiness only after the caller
  confirms the repeated claim ID in a later turn. If the caller corrects the
  ID, repeat the corrected ID and ask for confirmation again.
- After confirmation, call lookup_claim_story once for a claim explanation and
  answer only from its result.
- For coverage, prior-authorization, or cost-sharing questions, call
  lookup_coverage using the caller's exact service wording. Use find_provider
  only when the caller asks for a provider or the grounded benefit result
  recommends provider guidance.
- After confirmation, call screen_claim_readiness once for a readiness
  question. Describe it as a rules-based Claim Readiness screen, never as a
  prediction or probability.
- When the caller confirms that a recommended readiness action was taken, call
  record_corrective_intervention. Never say that recording it prevented a denial.
- A readiness risk band is a rules classification, not a probability.
  Data completeness describes the inputs, not predictive confidence.
- Never invent claim facts, coverage rules, denial reasons, readiness factors,
  provider availability, costs, or timelines. Copy factual values exactly from
  tool results.
- If the tool reports not_found, say so and ask the caller to re-check the ID.
- If a tool reports member_mismatch, ask the caller to re-check the claim and
  member IDs without revealing claim details.
- If the tool reports needs_escalation, tell the caller a claims specialist
  needs to review it and offer to connect them.
- If a benefit result is ambiguous, present its choices and ask the caller to
  clarify. If it is roi_required, do not share plan-specific detail.
- Do not diagnose medical conditions or make coverage promises.

Response style:
- Short spoken sentences. No markdown, bullet points, or symbols.
- Speak at a calm, measured pace, slightly slower than typical conversation,
  with brief natural pauses between ideas.
- Say dollar amounts and dates naturally.
- Summarize the outcome first, then offer more detail instead of reading
  every field.
""".strip()

_default_trace_store = InMemoryDelegationTraceStore()


def log_agent_route(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> None:
    """Log metadata for each root-agent routing decision.

    Tool arguments and result payloads are deliberately excluded because they
    can contain member or claim information.
    """

    del args

    logger.info(
        "Agent route agent=%s tool=%s invocation_id=%s session_id=%s",
        ROUTED_AGENT_BY_TOOL.get(tool.name, "unknown_specialist"),
        tool.name,
        tool_context.invocation_id,
        tool_context.session.id,
    )


def create_voice_orchestrator(
    settings: Settings | None = None,
    claims_repository: ClaimsRepository | None = None,
    model_name: str | None = None,
    member_records_client: MemberRecordsClient | None = None,
    events: EventLog | None = None,
    traces: TraceSink | None = None,
) -> LlmAgent:
    """Create the root agent that fronts the caller channel.

    Defaults to the live (audio-native) model for the voice WebSocket; pass
    ``model_name=settings.model_name`` for text channels, because live models
    reject the ``generateContent`` API that ``/run`` and ``/run_sse`` use.

    Claim Story uses a real ADK ``AgentTool`` specialist handoff. Its typed
    output is checked against the deterministic repository result; exceptions,
    malformed output, or grounding mismatches fail closed to the direct tool.
    """

    resolved_settings = settings or default_settings
    resolved_repository = claims_repository or create_claims_repository(
        resolved_settings
    )
    resolved_member_records = member_records_client or create_member_records_client(
        resolved_settings
    )
    claim_story_service = ClaimStoryService(resolved_repository)
    readiness_service = ClaimReadinessService(resolved_repository)
    resolved_events = events or event_log
    resolved_traces = traces or _default_trace_store
    direct_claim_tool = build_lookup_claim_story_tool(
        claim_story_service,
        enforce_member_context=True,
        events=resolved_events,
    )
    claim_story_specialist = create_claim_story_agent(
        resolved_settings,
        resolved_repository,
        agent_name="lookup_claim_story",
        enforce_member_context=True,
        events=resolved_events,
    )
    if model_name is None:
        # The live model is only served in some regions (us-central1 for this
        # project), which may differ from GOOGLE_CLOUD_LOCATION, so give the
        # live agent its own client pinned to the live model's location.
        model = Gemini(
            model=resolved_settings.live_model_name,
            client_kwargs={
                "vertexai": resolved_settings.google_genai_use_vertexai,
                "project": resolved_settings.google_cloud_project,
                "location": resolved_settings.live_model_location,
            },
        )
    else:
        model = model_name
    return LlmAgent(
        name="voice_orchestrator",
        description=(
            "Front-door member-services agent that safely coordinates ROI, Claim "
            "Story, Benefits Q&A, and Claim Readiness."
        ),
        model=model,
        instruction=VOICE_ORCHESTRATOR_INSTRUCTION,
        mode="chat",
        before_tool_callback=log_agent_route,
        tools=[
            build_establish_member_context_tool(resolved_member_records, resolved_events),
            TracedClaimStoryAgentTool(
                agent=claim_story_specialist,
                fallback_tool=direct_claim_tool,
                service=claim_story_service,
                trace_sink=resolved_traces,
            ),
            build_screen_claim_readiness_tool(
                readiness_service,
                enforce_member_context=True,
                events=resolved_events,
            ),
            build_record_corrective_intervention_tool(events=resolved_events),
            FunctionTool(lookup_coverage),
            FunctionTool(find_provider_tool),
        ],
    )
