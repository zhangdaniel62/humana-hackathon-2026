"""Benefits Q&A agent.

Public surface, by consumer:

* Orchestrator -> `benefits_agent` (wrap with ADK's AgentTool)
* UI           -> `BenefitsAnswer` (`.model_dump_json()`)
* Anyone       -> `answer_benefits_question(...)`, pure and LLM-free
* Integration  -> `AGENT_KEY`, `EVENT_TYPE`, `NETWORK_GAP_EVENT`, `StateKeys`,
                  `roi_permits_detail` (constants and one pure function)

Everything lives in `agent.py`. Importing this module does not construct the ADK
agent -- `benefits_agent` is resolved lazily so the deterministic core stays
usable without google-adk installed.
"""

from ..src.agents.benefits import (
    AGENT_KEY,
    EVENT_TYPE,
    NETWORK_GAP_EVENT,
    BenefitsAnswer,
    CostBreakdown,
    CoverageRulesClient,
    CsvBenefitsKB,
    MemberRecordsClient,
    ProviderDirectoryClient,
    ProviderResult,
    Resolution,
    Settings,
    StateKeys,
    answer_benefits_question,
    data_source,
    find_provider,
    get_coverage_rules_client,
    get_member_records_client,
    get_provider_directory_client,
    get_settings,
    roi_permits_detail,
)

__all__ = [
    "AGENT_KEY",
    "BenefitsAnswer",
    "CostBreakdown",
    "CoverageRulesClient",
    "CsvBenefitsKB",
    "EVENT_TYPE",
    "MemberRecordsClient",
    "NETWORK_GAP_EVENT",
    "ProviderDirectoryClient",
    "ProviderResult",
    "Resolution",
    "Settings",
    "StateKeys",
    "answer_benefits_question",
    "benefits_agent",
    "build_agent",
    "data_source",
    "find_provider",
    "get_coverage_rules_client",
    "get_member_records_client",
    "get_provider_directory_client",
    "get_settings",
    "roi_permits_detail",
]


def __getattr__(name: str):
    # Lazy so `import benefits` works without google-adk present.
    if name in {"benefits_agent", "build_agent"}:
        from ..src.agents import benefits as _agent

        return getattr(_agent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
