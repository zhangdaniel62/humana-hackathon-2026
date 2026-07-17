"""Opt-in credentialed ADK evaluation; never part of offline CI thresholds."""

from __future__ import annotations

from time import perf_counter

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..agents.claim_story import CLAIM_STORY_OUTPUT_KEY, create_claim_story_agent
from ..clients.claims import CsvClaimsRepository
from ..models import ClaimStoryResult
from ..settings import settings
from .harness import EvaluationCaseResult


async def run_live_claim_story_case() -> EvaluationCaseResult:
    """Measure one real model-backed specialist run against synthetic facts."""

    started = perf_counter()
    checks: dict[str, bool] = {}
    error_code: str | None = None
    runner: Runner | None = None
    try:
        sessions = InMemorySessionService()
        agent = create_claim_story_agent(settings, CsvClaimsRepository())
        runner = Runner(
            app_name="claim_assist_live_evaluation",
            agent=agent,
            session_service=sessions,
        )
        session = await sessions.create_session(
            app_name="claim_assist_live_evaluation",
            user_id="evaluation",
        )
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text='{"claim_id":"CLM000490"}')],
        )
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=message,
        ):
            pass
        updated = await sessions.get_session(
            app_name="claim_assist_live_evaluation",
            user_id=session.user_id,
            session_id=session.id,
        )
        assert updated is not None
        result = ClaimStoryResult.model_validate(updated.state[CLAIM_STORY_OUTPUT_KEY])
        checks = {
            "typed_result": True,
            "status": result.status.value == "success",
            "grounded_record": bool(
                result.story
                and result.story.grounding.table == "claims"
                and result.story.grounding.record_id == "CLM000490"
            ),
        }
    except Exception as exc:
        error_code = type(exc).__name__
        checks = checks or {"executed": False}
    finally:
        if runner is not None:
            await runner.close()
    return EvaluationCaseResult(
        case_id="live-adk-claim-story",
        category="live_adk",
        kind="live_claim_story",
        passed=bool(checks) and all(checks.values()) and error_code is None,
        latency_ms=round((perf_counter() - started) * 1_000, 3),
        checks=checks,
        error_code=error_code,
    )
