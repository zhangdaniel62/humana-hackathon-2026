from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from models import AgentEvent, EventType


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _boolean(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def load_claim_denial_events(path: str | Path) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["claim_status"].strip().lower() != "denied":
                continue
            claim_id = row["claim_id"]
            event_time = row["adjudication_date"] or row["submitted_date"]
            events.append(
                AgentEvent(
                    event_id=uuid5(NAMESPACE_URL, f"claim-denial:{claim_id}"),
                    timestamp=_timestamp(event_time),
                    session_id=f"historical-claim-{claim_id}",
                    agent="claim_story",
                    event_type=EventType.DENIAL_EXPLAINED,
                    member_id=row["member_id"],
                    claim_id=claim_id,
                    payload={
                        "denial_code": row["denial_code"],
                        "denial_reason": row["denial_reason"],
                        "denial_fixable": _boolean(row["denial_fixable"]),
                        "provider_id": row["provider_id"],
                        "provider_name": row["provider_name"],
                        "reprocessing_days_est": (
                            float(row["reprocessing_days_est"])
                            if row["reprocessing_days_est"]
                            else None
                        ),
                    },
                )
            )
    return sorted(events, key=lambda event: event.timestamp)


def load_compliance_flag_events(path: str | Path) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if _boolean(row["resolved"]):
                continue
            flag_id = row["flag_id"]
            entity_type = row["entity_type"]
            entity_id = row["entity_id"]
            events.append(
                AgentEvent(
                    event_id=uuid5(NAMESPACE_URL, f"compliance-flag:{flag_id}"),
                    timestamp=_timestamp(row["flag_date"]),
                    session_id=f"historical-flag-{flag_id}",
                    agent="sentinel_seed",
                    event_type=EventType.COMPLIANCE_FLAG_DETECTED,
                    member_id=entity_id if entity_type == "Member" else None,
                    claim_id=entity_id if entity_type == "Claim" else None,
                    payload={
                        "flag_id": flag_id,
                        "flag_type": row["flag_type"],
                        "severity": row["severity"].lower(),
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "metric_value": float(row["metric_value"]),
                        "metric_label": row["metric_label"],
                        "description": row["description"],
                        "recommended_action": row["recommended_action"],
                    },
                )
            )
    return sorted(events, key=lambda event: event.timestamp)
