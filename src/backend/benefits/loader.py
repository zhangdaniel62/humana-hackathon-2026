"""CSV -> models. stdlib only; loaded once and cached at module level."""

import csv
import os
from functools import lru_cache
from pathlib import Path

from .contract import PLAN_TYPES
from .models import CoverageRule, Member, Provider

DATASETS = Path(
    os.getenv("BENEFITS_DATASETS_DIR")
    or Path(__file__).resolve().parents[3] / "datasets"
)

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0", ""}


def parse_bool(raw: str) -> bool:
    """Parse the CSVs' lowercase 'true'/'false' strings.

    bool("false") is True, so the naive cast silently inverts every negative
    flag in the dataset -- including `covered`. Reject anything unrecognised
    rather than guessing.
    """
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"unparseable boolean: {raw!r}")


def _rows(name: str) -> list[dict[str, str]]:
    with (DATASETS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def load_rules() -> tuple[CoverageRule, ...]:
    rules = tuple(
        CoverageRule(
            rule_id=r["rule_id"],
            plan_type=r["plan_type"],
            cpt_code=r["cpt_code"],
            cpt_description=r["cpt_description"],
            covered=parse_bool(r["covered"]),
            prior_auth_required=parse_bool(r["prior_auth_required"]),
            cost_share_pct=int(r["cost_share_pct"]),
            copay=int(r["copay"]),
            notes=r["notes"],
        )
        for r in _rows("coverage_rules.csv")
    )
    _assert_grid(rules)
    return rules


def _assert_grid(rules: tuple[CoverageRule, ...]) -> None:
    """The 20x4 grid is total. Lookup relies on it, so fail loudly at load."""
    codes = {r.cpt_code for r in rules}
    if len(rules) != 80 or len({(r.plan_type, r.cpt_code) for r in rules}) != 80:
        raise AssertionError(f"expected 80 unique (plan, code) rules, got {len(rules)}")
    if len(codes) != 20:
        raise AssertionError(f"expected 20 distinct CPT codes, got {len(codes)}")
    for plan in PLAN_TYPES:
        have = {r.cpt_code for r in rules if r.plan_type == plan}
        if have != codes:
            raise AssertionError(f"plan {plan} is missing codes: {sorted(codes - have)}")


@lru_cache(maxsize=1)
def load_members() -> dict[str, Member]:
    return {
        r["member_id"]: Member(
            member_id=r["member_id"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            plan_type=r["plan_type"],
            pcp_id=r["pcp_id"],
            city=r["city"],
            state=r["state"],
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            language_preference=r["language_preference"],
        )
        for r in _rows("members.csv")
    }


@lru_cache(maxsize=1)
def load_providers() -> dict[str, Provider]:
    return {
        r["provider_id"]: Provider(
            provider_id=r["provider_id"],
            name=r["name"],
            specialty=r["specialty"],
            city=r["city"],
            state=r["state"],
            phone=r["phone"],
            network_status=r["network_status"],
            accepting_new_patients=parse_bool(r["accepting_new_patients"]),
            hospital_affiliation=r["hospital_affiliation"],
        )
        for r in _rows("providers.csv")
    }


@lru_cache(maxsize=1)
def rule_index() -> dict[tuple[str, str], CoverageRule]:
    """(plan_type, cpt_code) -> rule. Total over the grid; every hit succeeds."""
    return {(r.plan_type, r.cpt_code): r for r in load_rules()}


@lru_cache(maxsize=1)
def descriptions() -> dict[str, str]:
    """cpt_code -> canonical description (identical across all 4 plans)."""
    return {r.cpt_code: r.cpt_description for r in load_rules()}
