from pathlib import Path

from clients.mock import load_claim_denial_events, load_compliance_flag_events
from models import EventType


DATASETS = Path(__file__).parents[3] / "datasets"


def test_loads_supplied_claim_denials() -> None:
    events = load_claim_denial_events(DATASETS / "claims.csv")
    assert len(events) == 212
    assert all(event.event_type is EventType.DENIAL_EXPLAINED for event in events)
    assert all(event.claim_id and event.member_id for event in events)
    assert events == sorted(events, key=lambda event: event.timestamp)


def test_loads_unresolved_compliance_flags() -> None:
    events = load_compliance_flag_events(DATASETS / "compliance_flags.csv")
    assert len(events) == 312
    assert all(event.event_type is EventType.COMPLIANCE_FLAG_DETECTED for event in events)
