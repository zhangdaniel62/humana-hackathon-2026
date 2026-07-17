"""A real ADK AgentTool handoff with deterministic fail-closed fallback."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.agent_tool import AgentTool
from pydantic import PrivateAttr

from ..delegation.store import TraceSink
from ..models import ClaimStoryResult, DelegationTrace
from ..services.claim_story import ClaimStoryService
from .claim_story import CLAIM_STORY_STATE_KEY
from .session_context import (
    record_finding,
    record_intent,
    roi_permits_member_detail,
)

logger = logging.getLogger(__name__)


class TracedClaimStoryAgentTool(AgentTool):
    """Invoke the specialist agent, validate grounding, and fail closed."""

    _fallback_tool: FunctionTool = PrivateAttr()
    _service: ClaimStoryService = PrivateAttr()
    _trace_sink: TraceSink = PrivateAttr()

    def __init__(
        self,
        *,
        agent,
        fallback_tool: FunctionTool,
        service: ClaimStoryService,
        trace_sink: TraceSink,
    ) -> None:
        super().__init__(agent=agent)
        self._fallback_tool = fallback_tool
        self._service = service
        self._trace_sink = trace_sink

    @property
    def func(self):
        """Expose the deterministic path for focused non-runner unit tests."""

        return self._fallback_tool.func

    async def run_async(self, *, args: dict, tool_context: ToolContext):
        trace_id = str(uuid4())
        started_at = datetime.now(UTC)
        started_clock = monotonic()
        outcome = "success"
        error_code: str | None = None
        try:
            if not roi_permits_member_detail(tool_context.state):
                outcome = "blocked"
                return self._fallback_tool.func(args["claim_id"], tool_context)

            raw_result = await super().run_async(
                args=args, tool_context=tool_context
            )
            result = ClaimStoryResult.model_validate(raw_result)
            canonical = self._service.prepare(args["claim_id"])
            if not self._same_grounded_record(result, canonical):
                raise ValueError("specialist result failed deterministic grounding check")
            payload = result.model_dump(mode="json")
            tool_context.state[CLAIM_STORY_STATE_KEY] = payload
            record_finding(tool_context.state, "claim_story", payload)
            record_intent(tool_context.state, "claim_story")
            return payload
        except Exception as exc:
            outcome = "fallback"
            error_code = type(exc).__name__
            logger.warning(
                "Claim Story specialist delegation failed; using deterministic fallback",
                exc_info=exc,
            )
            return self._fallback_tool.func(args["claim_id"], tool_context)
        finally:
            completed_at = datetime.now(UTC)
            try:
                self._trace_sink.record(
                    DelegationTrace(
                        trace_id=trace_id,
                        session_id=str(
                            tool_context.state.get("session_id") or "unscoped"
                        ),
                        work_item_id=tool_context.state.get("work_item_id"),
                        specialist="claim_story_agent",
                        started_at=started_at,
                        completed_at=completed_at,
                        latency_ms=round((monotonic() - started_clock) * 1_000, 3),
                        outcome=outcome,
                        error_code=error_code,
                    )
                )
            except Exception:
                logger.exception("Could not persist delegation trace metadata")

    @staticmethod
    def _same_grounded_record(
        result: ClaimStoryResult, canonical: ClaimStoryResult
    ) -> bool:
        if result.status is not canonical.status:
            return False
        if result.story is None or canonical.story is None:
            return result.story is canonical.story
        return (
            result.story.claim_id == canonical.story.claim_id
            and result.story.member_id == canonical.story.member_id
            and result.story.current_status is canonical.story.current_status
            and result.story.billed_amount == canonical.story.billed_amount
            and result.story.paid_amount == canonical.story.paid_amount
            and result.story.grounding == canonical.story.grounding
        )
