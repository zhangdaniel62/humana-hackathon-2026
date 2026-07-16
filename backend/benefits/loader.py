"""Facade over the data clients.

Everything above this module (kb.py, providers.py, answer.py) calls these
functions and is unaware of whether the rows came from CSV or BigQuery. Swapping
the backend touches only `settings.data_source`.

Loaded once per process and cached: the whole dataset is ~330 rows.
"""

from functools import lru_cache

from .clients import (
    get_coverage_rules_client,
    get_member_records_client,
    get_provider_directory_client,
)
from .clients.mapping import coerce_bool as parse_bool  # re-exported; see note below
from .contract import PLAN_TYPES
from .models import CoverageRule, Member, Provider
from .settings import get_settings

# `parse_bool` predates the client layer and is still the clearest name at call
# sites; coerce_bool is the same function generalised to BigQuery's native types.

DATASETS = get_settings().datasets_dir


# Clients are cached, not just their rows: constructing one runs a BigQuery
# query, so a second construction would mean a second round trip per table.
@lru_cache(maxsize=1)
def _rules_client():
    return get_coverage_rules_client()


@lru_cache(maxsize=1)
def _members_client():
    return get_member_records_client()


@lru_cache(maxsize=1)
def _providers_client():
    return get_provider_directory_client()


@lru_cache(maxsize=1)
def load_rules() -> tuple[CoverageRule, ...]:
    rules = _rules_client().fetch_all()
    _assert_grid(rules)
    return rules


def _assert_grid(rules: tuple[CoverageRule, ...]) -> None:
    """The 20x4 grid is total. Lookup relies on it, so fail loudly at load.

    This runs against whichever backend served the rows, so a BigQuery table that
    is stale, filtered, or pointed at the wrong dataset fails here rather than
    surfacing as a KeyError mid-demo.
    """
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
    return _members_client().fetch_all()


@lru_cache(maxsize=1)
def load_providers() -> dict[str, Provider]:
    return _providers_client().fetch_all()


@lru_cache(maxsize=1)
def rule_index() -> dict[tuple[str, str], CoverageRule]:
    """(plan_type, cpt_code) -> rule. Total over the grid; every hit succeeds."""
    return {(r.plan_type, r.cpt_code): r for r in load_rules()}


@lru_cache(maxsize=1)
def descriptions() -> dict[str, str]:
    """cpt_code -> canonical description (identical across all 4 plans)."""
    return {r.cpt_code: r.cpt_description for r in load_rules()}


def data_source() -> str:
    """Which backend actually served the coverage rules: csv | bigquery | csv_fallback.

    Reported on every answer, so a fallback is visible rather than silent.
    """
    return _rules_client().source


def reset_cache() -> None:
    """Drop every cached client and table. For tests and post-config-change reloads."""
    for fn in (
        _rules_client,
        _members_client,
        _providers_client,
        load_rules,
        load_members,
        load_providers,
        rule_index,
        descriptions,
    ):
        fn.cache_clear()


__all__ = [
    "DATASETS",
    "data_source",
    "descriptions",
    "load_members",
    "load_providers",
    "load_rules",
    "parse_bool",
    "reset_cache",
    "rule_index",
]
