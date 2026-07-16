"""ADK agent definition.

Deliberately thin. Coverage is decided in answer.py; this layer only narrates and
translates. `output_schema` is NOT used: the ADK docs note that combining it with
tools is only reliable on specific models (Gemini 3.0), and it isn't needed --
every fact on the card is already hard data from the tool return, so the card is
assembled from state rather than parsed out of the model's prose.

Import-safe without an API key: constructing the agent performs no network I/O.
"""

import os

from google.adk.agents import LlmAgent

from .prompts import SYSTEM_PROMPT
from .tools import find_provider, lookup_coverage

MODEL = os.getenv("BENEFITS_MODEL", "gemini-flash-latest")

DESCRIPTION = (
    "Answers member questions about coverage, prior authorization, and cost "
    "sharing for medical services, grounded in the plan's coverage rules."
)


def build_agent(model: str | None = None) -> LlmAgent:
    return LlmAgent(
        model=model or MODEL,
        name="benefits_qa",
        description=DESCRIPTION,
        instruction=SYSTEM_PROMPT,
        tools=[lookup_coverage, find_provider],
    )


#: Import this from the orchestrator and wrap it:
#:     from google.adk.tools.agent_tool import AgentTool
#:     AgentTool(agent=benefits_agent)
#: Agent-as-tool keeps the orchestrator in control, unlike description-transfer
#: sub_agents, which hand off the turn entirely.
benefits_agent = build_agent()
