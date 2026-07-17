"""Offline evaluation of grounding, ROI safety, and routing contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..agents.claim_story import build_lookup_claim_story_tool
from ..agents.session_context import build_establish_member_context_tool
from ..clients.claims import CsvClaimsRepository
from ..clients.member_records import CsvMemberRecordsClient
from ..events import EventLog
from ..services.claim_readiness import ClaimReadinessService
from ..services.claim_story import ClaimStoryService


class EvaluationCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    kind: str
    passed: bool
    latency_ms: float = Field(ge=0)
    checks: dict[str, bool]
    error_code: str | None = None


class EvaluationCategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    corpus_version: str
    data_label: str
    mode: str
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    categories: dict[str, EvaluationCategorySummary]
    minimum_pass_rate: float = Field(ge=0, le=1)
    thresholds_met: bool
    live_evaluation: str
    cases: list[EvaluationCaseResult]

    def to_markdown(self) -> str:
        lines = [
            "# Claim Assist evaluation report",
            "",
            f"- Corpus: `{self.corpus_version}`",
            f"- Mode: `{self.mode}`",
            f"- Result: **{self.passed}/{self.total} passed ({self.pass_rate:.1%})**",
            f"- Threshold: {self.minimum_pass_rate:.1%} — "
            f"{'met' if self.thresholds_met else 'not met'}",
            f"- Latency: p50 {self.p50_latency_ms:.3f} ms; "
            f"p95 {self.p95_latency_ms:.3f} ms",
            f"- Live ADK evaluation: {self.live_evaluation}",
            "",
            "| Category | Passed | Total | Pass rate |",
            "|---|---:|---:|---:|",
        ]
        for name, summary in sorted(self.categories.items()):
            lines.append(
                f"| {name} | {summary.passed} | {summary.total} | "
                f"{summary.pass_rate:.1%} |"
            )
        lines.extend(
            [
                "",
                "| Case | Category | Result | Latency (ms) |",
                "|---|---|---|---:|",
            ]
        )
        for case in self.cases:
            lines.append(
                f"| {case.case_id} | {case.category} | "
                f"{'pass' if case.passed else 'fail'} | {case.latency_ms:.3f} |"
            )
        lines.extend(
            [
                "",
                "Offline routing cases validate the declared deterministic routing "
                "contract, not live-model routing accuracy. Network latency is never "
                "used as an offline threshold.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass
class _Context:
    state: dict[str, Any]


class EvaluationHarness:
    def __init__(self) -> None:
        self.repository = CsvClaimsRepository()
        self.claim_story = ClaimStoryService(self.repository)
        self.readiness = ClaimReadinessService(self.repository)

    def run(
        self,
        corpus_path: Path,
        *,
        minimum_pass_rate: float = 1.0,
    ) -> EvaluationReport:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        results = [self._run_case(case) for case in corpus["cases"]]
        return self.build_report(
            results,
            corpus_version=corpus["corpus_version"],
            data_label=corpus["data_label"],
            minimum_pass_rate=minimum_pass_rate,
        )

    def _run_case(self, case: dict[str, Any]) -> EvaluationCaseResult:
        started = perf_counter()
        checks: dict[str, bool] = {}
        error_code: str | None = None
        try:
            kind = case["kind"]
            if kind == "claim_story":
                result = self.claim_story.prepare(case["claim_id"])
                checks = {
                    "status": result.status.value == case["expected_status"],
                    "grounded_record": bool(
                        result.story
                        and result.story.grounding.table == "claims"
                        and result.story.grounding.record_id
                        == case["expected_record_id"]
                    ),
                }
            elif kind == "readiness":
                result = self.readiness.evaluate(case["claim_id"])
                factors = result.assessment.factors if result.assessment else []
                checks = {
                    "status": result.status.value == case["expected_status"],
                    "reviewed_rules": sorted(factor.rule_id for factor in factors)
                    == sorted(case["expected_rule_ids"]),
                    "methodology": bool(
                        result.assessment
                        and result.assessment.methodology
                        == "reviewed_deterministic_rules"
                    ),
                }
            elif kind == "roi":
                context = _Context(state={"caller_id": case["caller_id"]})
                result = build_establish_member_context_tool(
                    CsvMemberRecordsClient(), EventLog()
                ).func(case["caller_name"], case["subject_member_id"], context)
                checks = {
                    "roi_status": result["roi"]["status"]
                    == case["expected_roi_status"]
                }
            elif kind == "roi_blocked_claim":
                context = _Context(state={})
                establish = build_establish_member_context_tool(
                    CsvMemberRecordsClient(), EventLog()
                )
                establish.func(
                    case["caller_name"], case["subject_member_id"], context
                )
                blocked = build_lookup_claim_story_tool(
                    self.claim_story,
                    enforce_member_context=True,
                    events=EventLog(),
                ).func(case["claim_id"], context)
                checks = {
                    "blocked": blocked["status"] == case["expected_status"],
                    "no_member_details": not any(
                        key in blocked
                        for key in ("story", "member_id", "provider_name", "denial")
                    ),
                }
            elif kind == "routing_contract":
                checks = {
                    "route": offline_route(case["utterance"])
                    == case["expected_route"]
                }
            else:
                raise ValueError("unsupported evaluation case kind")
        except Exception as exc:
            error_code = type(exc).__name__
            checks = checks or {"executed": False}
        return EvaluationCaseResult(
            case_id=case["case_id"],
            category=case["category"],
            kind=case["kind"],
            passed=bool(checks) and all(checks.values()) and error_code is None,
            latency_ms=round((perf_counter() - started) * 1_000, 3),
            checks=checks,
            error_code=error_code,
        )

    @staticmethod
    def build_report(
        results: list[EvaluationCaseResult],
        *,
        corpus_version: str,
        data_label: str,
        minimum_pass_rate: float,
        live_evaluation: str = "skipped; opt in with --live",
    ) -> EvaluationReport:
        by_category: dict[str, list[EvaluationCaseResult]] = {}
        for result in results:
            by_category.setdefault(result.category, []).append(result)
        categories = {
            category: EvaluationCategorySummary(
                total=len(items),
                passed=sum(item.passed for item in items),
                pass_rate=sum(item.passed for item in items) / len(items),
            )
            for category, items in by_category.items()
        }
        latencies = sorted(item.latency_ms for item in results) or [0.0]
        passed = sum(item.passed for item in results)
        pass_rate = passed / len(results) if results else 0.0
        category_thresholds_met = all(
            summary.pass_rate >= minimum_pass_rate
            for summary in categories.values()
        )
        return EvaluationReport(
            corpus_version=corpus_version,
            data_label=data_label,
            mode="offline_deterministic",
            total=len(results),
            passed=passed,
            pass_rate=pass_rate,
            p50_latency_ms=round(median(latencies), 3),
            p95_latency_ms=round(_percentile(latencies, 0.95), 3),
            categories=categories,
            minimum_pass_rate=minimum_pass_rate,
            thresholds_met=(
                pass_rate >= minimum_pass_rate and category_thresholds_met
            ),
            live_evaluation=live_evaluation,
            cases=results,
        )


def offline_route(utterance: str) -> str:
    """Transparent contract baseline; this is not an LLM accuracy claim."""

    normalized = utterance.casefold()
    if "readiness" in normalized or "readiness risk" in normalized:
        return "claim_readiness"
    if "covered" in normalized or "coverage" in normalized or "benefit" in normalized:
        return "benefits"
    if "claim" in normalized:
        return "claim_story"
    return "clarify"


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    fraction = rank - lower
    return values[lower] + (values[upper] - values[lower]) * fraction
