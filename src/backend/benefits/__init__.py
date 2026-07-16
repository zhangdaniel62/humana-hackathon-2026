"""Benefits Q&A agent.

Public surface, by consumer:

* Orchestrator -> `benefits_agent` (wrap with ADK's AgentTool)
* UI           -> `BenefitsAnswer` (`.model_dump_json()`)
* Anyone       -> `answer_benefits_question(...)`, pure and LLM-free
* Integration  -> `contract` (constants only; imports nothing)

Importing this module does not construct the ADK agent -- `agent` is resolved
lazily so the deterministic core stays usable without google-adk installed.
"""

from . import contract, events
from .answer import answer_benefits_question
from .contract import AGENT_KEY, EVENT_TYPE, NETWORK_GAP_EVENT, StateKeys, roi_permits_detail
from .kb import CsvBenefitsKB
from .models import BenefitsAnswer, CostBreakdown, ProviderResult, Resolution
from .providers import find_provider

__all__ = [
    "AGENT_KEY",
    "BenefitsAnswer",
    "CostBreakdown",
    "CsvBenefitsKB",
    "EVENT_TYPE",
    "NETWORK_GAP_EVENT",
    "ProviderResult",
    "Resolution",
    "StateKeys",
    "answer_benefits_question",
    "benefits_agent",
    "build_agent",
    "contract",
    "events",
    "find_provider",
    "roi_permits_detail",
]


def __getattr__(name: str):
    # Lazy so `import benefits` works without google-adk present.
    if name in {"benefits_agent", "build_agent"}:
        from . import agent as _agent

        return getattr(_agent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
