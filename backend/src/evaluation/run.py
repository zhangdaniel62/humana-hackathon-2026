"""CLI entry point for CI-ready evaluation and stable JSON/Markdown reports."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .harness import EvaluationHarness

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = BACKEND_DIR / "evaluation" / "corpus.json"
DEFAULT_OUTPUT = BACKEND_DIR / "artifacts" / "evaluation"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--minimum-pass-rate", type=float, default=1.0)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one credentialed Vertex/ADK specialist case in addition to offline cases.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.minimum_pass_rate <= 1:
        raise SystemExit("--minimum-pass-rate must be between 0 and 1")
    harness = EvaluationHarness()
    report = harness.run(
        args.corpus,
        minimum_pass_rate=args.minimum_pass_rate,
    )
    if args.live:
        from .live import run_live_claim_story_case

        live_result = asyncio.run(run_live_claim_story_case())
        report = harness.build_report(
            [*report.cases, live_result],
            corpus_version=report.corpus_version,
            data_label=report.data_label,
            minimum_pass_rate=args.minimum_pass_rate,
            live_evaluation="executed by explicit --live opt-in",
        ).model_copy(update={"mode": "offline_plus_live_adk"})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "latest.md").write_text(
        report.to_markdown(), encoding="utf-8"
    )
    print(
        f"Evaluation: {report.passed}/{report.total} passed; "
        f"thresholds {'met' if report.thresholds_met else 'not met'}."
    )
    return 0 if report.thresholds_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
