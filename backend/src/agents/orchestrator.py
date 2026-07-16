"""Voice-facing ADK root agent for the browser-mic call flow."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini

from ..clients.claims import BigQueryClaimsRepository, ClaimsRepository
from ..services.claim_story import ClaimStoryService
from ..settings import Settings, settings as default_settings
from .claim_story import build_lookup_claim_story_tool

VOICE_ORCHESTRATOR_INSTRUCTION = """
You are the Claim Assist voice agent for a health-plan member services line.
You are speaking with a caller out loud, so respond the way a helpful phone
representative would.

Conversation rules:
- Greet the caller briefly and ask how you can help.
- For any question about a specific claim, call lookup_claim_story with the
  exact claim ID and answer only from what it returns.
- Read the claim ID back to the caller to confirm it before looking it up.
- Never invent claim facts, coverage rules, denial reasons, or timelines.
  Copy IDs, dates, codes, amounts, required actions, and estimates exactly
  from the tool result.
- If the tool reports not_found, say so and ask the caller to re-check the ID.
- If the tool reports needs_escalation, tell the caller a claims specialist
  needs to review it and offer to connect them.
- Do not diagnose medical conditions or make coverage promises.

Voice style:
- Short spoken sentences. No markdown, bullet points, or symbols.
- Say dollar amounts and dates naturally.
- Summarize the outcome first, then offer more detail instead of reading
  every field.
""".strip()


def create_voice_orchestrator(
    settings: Settings | None = None,
    claims_repository: ClaimsRepository | None = None,
    model_name: str | None = None,
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
    resolved_repository = claims_repository or BigQueryClaimsRepository(
        resolved_settings
    )
    service = ClaimStoryService(resolved_repository)
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
            "Front-door voice agent that greets callers and answers claim "
            "questions from grounded claim-story facts."
        ),
        model=model,
        instruction=VOICE_ORCHESTRATOR_INSTRUCTION,
        mode="chat",
        tools=[build_lookup_claim_story_tool(service)],
    )
