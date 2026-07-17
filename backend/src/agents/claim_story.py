"""Google ADK claim-story subagent."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.tools import FunctionTool, ToolContext
from google.genai.types import GenerateContentConfig

from ..clients.claims import ClaimsRepository, create_claims_repository
from ..events import EventLog, event_log
from ..models import AgentEvent, EventType
from ..models.claims import ClaimStoryRequest, ClaimStoryResult
from ..services.claim_story import ClaimStoryService
from ..settings import Settings, settings as default_settings
from .session_context import (
    SUBJECT_MEMBER_ID_KEY,
    member_mismatch_payload,
    record_finding,
    record_intent,
    roi_blocked_payload,
    roi_permits_member_detail,
)

CLAIM_STORY_STATE_KEY = "claim_story.prepared"
CLAIM_STORY_OUTPUT_KEY = "claim_story.result"

CLAIM_STORY_INSTRUCTION = """
You are the Claim Story specialist. Your input is JSON matching
ClaimStoryRequest and contains one exact claim_id.

Required process:
1. Call lookup_claim_story exactly once with the supplied claim_id.
2. Use only the returned object. Never infer or invent claim facts.
3. Return JSON matching ClaimStoryResult.

Rules:
- Copy claim IDs, member IDs, status, dates, codes, amounts, fixability,
  required actions, reprocessing estimates, confidence, grounding, and result
  status exactly as returned by the tool.
- You may make only the summary and timeline explanations more concise and
  member-friendly. Do not change their factual meaning.
- Preserve not_found and needs_escalation outcomes. Never turn them into success.
- Do not diagnose medical conditions or make coverage promises.
- Do not call any other tool and do not perform a member lookup.
""".strip()


def build_lookup_claim_story_tool(
    service: ClaimStoryService,
    *,
    enforce_member_context: bool = False,
    events: EventLog | None = None,
) -> FunctionTool:
    """Build the deterministic claim-story lookup tool shared by agents."""

    resolved_events = events or event_log

    def lookup_claim_story(
        claim_id: str,
        tool_context: ToolContext,
    ) -> dict:
        """Fetch one exact claim and prepare grounded claim-story facts."""

        request = ClaimStoryRequest(claim_id=claim_id)
        if enforce_member_context and not roi_permits_member_detail(
            tool_context.state
        ):
            payload = roi_blocked_payload(tool_context.state)
            tool_context.state[CLAIM_STORY_STATE_KEY] = payload
            record_finding(tool_context.state, "claim_story", payload)
            record_intent(tool_context.state, "claim_story")
            return payload

        result = service.prepare(request.claim_id)
        payload = result.model_dump(mode="json")
        story = payload.get("story")
        subject_member_id = tool_context.state.get(SUBJECT_MEMBER_ID_KEY)
        if (
            enforce_member_context
            and story
            and subject_member_id
            and story["member_id"] != subject_member_id
        ):
            payload = member_mismatch_payload(request.claim_id)
            tool_context.state[CLAIM_STORY_STATE_KEY] = payload
            record_finding(tool_context.state, "claim_story", payload)
            record_intent(tool_context.state, "claim_story")
            return payload

        tool_context.state[CLAIM_STORY_STATE_KEY] = payload
        record_finding(tool_context.state, "claim_story", payload)
        record_intent(tool_context.state, "claim_story")
        session_id = tool_context.state.get("session_id")
        if session_id and story:
            denial = story.get("denial")
            if denial:
                resolved_events.publish_nowait(
                    AgentEvent(
                        session_id=str(session_id),
                        agent="claim_story",
                        event_type=EventType.DENIAL_EXPLAINED,
                        member_id=story["member_id"],
                        claim_id=story["claim_id"],
                        payload={
                            "denial_code": denial["code"],
                            "denial_reason": denial["reason"],
                            "cause_category": denial["code"],
                            "synthetic": True,
                        },
                    )
                )
            if payload["status"] == "needs_escalation":
                resolved_events.publish_nowait(
                    AgentEvent(
                        session_id=str(session_id),
                        agent="claim_story",
                        event_type=EventType.ESCALATION_TRIGGERED,
                        member_id=story["member_id"],
                        claim_id=story["claim_id"],
                        payload={
                            "reason": payload["message"],
                            "severity": "high",
                            "recommended_action": "Route to a claims specialist.",
                            "synthetic": True,
                        },
                    )
                )
        return payload

    return FunctionTool(lookup_claim_story)


def create_claim_story_agent(
    settings: Settings | None = None,
    repository: ClaimsRepository | None = None,
    *,
    model: str | BaseLlm | None = None,
    agent_name: str = "claim_story_agent",
    enforce_member_context: bool = False,
    events: EventLog | None = None,
) -> LlmAgent:
    """Create a standalone, structured-output claim-story ADK agent."""

    resolved_settings = settings or default_settings
    resolved_repository = repository or create_claims_repository(resolved_settings)
    service = ClaimStoryService(resolved_repository)

    return LlmAgent(
        name=agent_name,
        description=(
            "Explains the lifecycle and current outcome of one exact claim using "
            "grounded BigQuery facts."
        ),
        model=model or resolved_settings.model_name,
        instruction=CLAIM_STORY_INSTRUCTION,
        tools=[
            build_lookup_claim_story_tool(
                service,
                enforce_member_context=enforce_member_context,
                events=events,
            )
        ],
        input_schema=ClaimStoryRequest,
        output_schema=ClaimStoryResult,
        output_key=CLAIM_STORY_OUTPUT_KEY,
        # ADK 2.4 requires every LlmAgent executed by Runner—including agents
        # invoked through AgentTool—to use chat mode. With include_contents set
        # to "none", each invocation still behaves as an isolated claim lookup.
        mode="chat",
        include_contents="none",
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
        ),
    )
