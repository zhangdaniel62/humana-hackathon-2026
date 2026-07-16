from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.agents import SentinelAgent
from src.clients.mock import load_claim_denial_events, load_compliance_flag_events
from src.events import EventLog


DEFAULT_DATASETS = Path(__file__).resolve().parents[1] / "datasets"


async def run(dataset_directory: Path, output: Path | None) -> None:
    event_log = EventLog()
    sentinel = SentinelAgent(event_log)
    await sentinel.start()

    events = [
        *load_claim_denial_events(dataset_directory / "claims.csv"),
        *load_compliance_flag_events(dataset_directory / "compliance_flags.csv"),
    ]
    for event in sorted(events, key=lambda item: item.timestamp):
        event_log.publish_nowait(event)

    await sentinel.stop()
    snapshot = sentinel.snapshot()
    rendered = snapshot.model_dump_json(indent=2)
    if output is not None:
        output.write_text(rendered, encoding="utf-8")

    print(f"Processed events: {snapshot.processed_event_count}")
    print(f"Active alerts: {snapshot.active_alert_count}")
    for alert in snapshot.alerts[:10]:
        print(f"[{alert.severity.value.upper()}] {alert.title}: {alert.description}")
    if output is not None:
        print(f"Snapshot written to: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay data through Sentinel")
    parser.add_argument(
        "--datasets",
        type=Path,
        default=DEFAULT_DATASETS,
        help="Directory containing claims.csv and compliance_flags.csv",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON snapshot path")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(run(arguments.datasets, arguments.output))
