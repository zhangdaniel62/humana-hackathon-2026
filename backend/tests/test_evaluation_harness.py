"""Evaluation corpus coverage, reporting, and threshold enforcement."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.harness import EvaluationHarness
from src.evaluation.run import DEFAULT_CORPUS, main


def test_offline_corpus_executes_every_case_and_meets_thresholds() -> None:
    corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))

    report = EvaluationHarness().run(DEFAULT_CORPUS)

    assert report.total == len(corpus["cases"])
    assert report.pass_rate == 1.0
    assert report.thresholds_met is True
    assert set(report.categories) == {
        "grounding",
        "roi",
        "routing_contract",
        "safety",
    }
    assert report.p95_latency_ms >= report.p50_latency_ms >= 0
    assert "not live-model routing accuracy" in report.to_markdown()


def test_cli_writes_stable_reports_and_fails_an_unmet_threshold(tmp_path) -> None:
    corpus = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))
    corpus["cases"][0]["expected_status"] = "not_found"
    failing_corpus = tmp_path / "failing.json"
    failing_corpus.write_text(json.dumps(corpus), encoding="utf-8")
    output = tmp_path / "reports"

    exit_code = main(
        [
            "--corpus",
            str(failing_corpus),
            "--output-dir",
            str(output),
            "--minimum-pass-rate",
            "1.0",
        ]
    )

    assert exit_code == 1
    report = json.loads((output / "latest.json").read_text(encoding="utf-8"))
    assert report["thresholds_met"] is False
    assert (output / "latest.md").is_file()


def test_report_contains_no_environment_paths_or_case_payloads(tmp_path) -> None:
    output = tmp_path / "reports"

    assert main(["--output-dir", str(output)]) == 0

    report_text = (output / "latest.json").read_text(encoding="utf-8")
    assert str(Path.home()) not in report_text
    assert "Unknown Caller" not in report_text
    assert '"utterance"' not in report_text
