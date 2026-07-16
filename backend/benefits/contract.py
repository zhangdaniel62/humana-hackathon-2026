"""Integration seam for the Benefits Q&A agent.

Deliberately has no imports and no logic: the orchestrator and UI can import
these symbols without pulling in ADK, pydantic, or the CSV loader.
"""

from typing import Final


class StateKeys:
    """Keys the Benefits agent reads from / writes to ADK session state."""

    # read
    SUBJECT_MEMBER_ID: Final = "subject_member_id"
    ROI_STATUS: Final = "roi_status"
    CALLER_NAME: Final = "caller_name"
    SESSION_ID: Final = "session_id"

    # write
    AGENT_FINDINGS: Final = "agent_findings"  # -> [...][AGENT_KEY]

    # internal to this agent; the deterministic card is built from this
    LAST_LOOKUP: Final = "benefits:last_lookup"


AGENT_KEY: Final = "benefits_qa"

EVENT_TYPE: Final = "coverage_question_answered"
NETWORK_GAP_EVENT: Final = "network_gap_detected"

# ROI states that permit member-specific coverage detail. Anything else --
# "missing", "expired", None, or an unrecognised value -- fails closed.
ROI_ALLOWED: Final = frozenset({"verified", "not_required"})

PLAN_TYPES: Final = ("DSNP", "HMO", "MAPD", "PPO")


def roi_permits_detail(roi_status: str | None) -> bool:
    """Fail closed: only explicitly allowed statuses unlock member detail."""
    return roi_status in ROI_ALLOWED
