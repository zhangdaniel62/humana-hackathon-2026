"""Shared ADK root agent for live voice and typed Claim Assist channels."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool

from ..clients.claims import ClaimsRepository, create_claims_repository
from ..clients.member_records import (
    MemberRecordsClient,
    create_member_records_client,
)
from ..services.claim_readiness import ClaimReadinessService
from ..services.claim_story import ClaimStoryService
from ..settings import Settings, settings as default_settings
from .benefits import find_provider_tool, lookup_coverage
from .claim_readiness import build_screen_claim_readiness_tool
from .claim_story import build_lookup_claim_story_tool
from .session_context import build_establish_member_context_tool

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
- Say dollar amounts and dates naturally.
- Summarize the outcome first, then offer more detail instead of reading
  every field.
""".strip()


def create_voice_orchestrator(
    settings: Settings | None = None,
    claims_repository: ClaimsRepository | None = None,
    model_name: str | None = None,
    member_records_client: MemberRecordsClient | None = None,
) -> LlmAgent:
    """Create the root agent that fronts the caller channel.

    Defaults to the live (audio-native) model for the voice WebSocket; pass
    ``model_name=settings.model_name`` for text channels, because live models
    reject the ``generateContent`` API that ``/run`` and ``/run_sse`` use.

    The orchestrator narrates directly from the deterministic
    ``lookup_claim_story`` tool rather than delegating to the structured
    claim-story agent: nesting an output-schema agent as a tool forces its
    LLM to re-emit the whole ClaimStoryResult JSON verbatim, which is
    unreliable (truncation and repetition loops observed with flash models).
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
        tools=[
            build_establish_member_context_tool(resolved_member_records),
            build_lookup_claim_story_tool(
                claim_story_service,
                enforce_member_context=True,
            ),
            build_screen_claim_readiness_tool(
                readiness_service,
                enforce_member_context=True,
            ),
            FunctionTool(lookup_coverage),
            FunctionTool(find_provider_tool),
        ],
    )
