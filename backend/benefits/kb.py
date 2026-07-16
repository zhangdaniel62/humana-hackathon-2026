"""Resolve free-text service queries to coverage rules. No LLM, no network."""

import re
from functools import lru_cache
from typing import Protocol

from .aliases import ALIASES, AMBIGUITY_GROUPS
from .contract import PLAN_TYPES
from .loader import descriptions, load_rules, rule_index
from .models import CoverageLookupResult, CoverageRule, Resolution

_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return f" {_PUNCT.sub(' ', text.lower()).strip()} "


@lru_cache(maxsize=1)
def all_codes() -> frozenset[str]:
    return frozenset(descriptions())


@lru_cache(maxsize=1)
def _code_re() -> re.Pattern[str]:
    """Match against the actual code set, not against a shape.

    r'\\d{5}' misses G0444; r'[A-Z]?\\d{4,5}' matches zip codes, ages and dollar
    amounts. The set is closed, so enumerate it -- longest first so G0444 can't
    be shadowed.
    """
    codes = sorted(all_codes(), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(c) for c in codes) + r")\b", re.IGNORECASE)


# A code-shaped token that is not one of ours. Checked only after _code_re misses,
# so it can never shadow a real code.
_CODE_SHAPED = re.compile(r"\b([A-Z]\d{4}|\d{5})\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _phrase_index() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Every known phrase -> the codes it names, longest phrase first.

    Aliases, ambiguity groups and canonical CSV descriptions share one index so
    that specificity wins globally: "total knee replacement" (an alias for 27447)
    beats the broad "knee" ambiguity group purely by being longer. Checking groups
    in a separate earlier pass would make that query ambiguous, which is wrong.
    """
    phrases: dict[str, tuple[str, ...]] = {}

    for code, desc in descriptions().items():
        phrases[normalize(desc).strip()] = (code,)
    for code, aliases in ALIASES.items():
        for a in aliases:
            phrases[normalize(a).strip()] = (code,)
    # Groups are authored last but never clobber a longer alias, since lookup is
    # by length. A group and an alias may share a phrase only by author error.
    for phrase, codes in AMBIGUITY_GROUPS.items():
        phrases[normalize(phrase).strip()] = codes

    return tuple(sorted(phrases.items(), key=lambda kv: len(kv[0]), reverse=True))


class BenefitsKB(Protocol):
    def resolve(self, query: str) -> CoverageLookupResult: ...
    def lookup(self, query: str, plan_type: str) -> CoverageLookupResult: ...
    def rule_for(self, cpt_code: str, plan_type: str) -> CoverageRule: ...


class CsvBenefitsKB:
    """The only source of coverage truth.

    Deliberately never reads claims.csv: 50/880 claims disagree with
    coverage_rules on prior_auth_required and 99 claims exist for services the
    member's plan marks not covered. Mixing them would let the agent contradict
    itself inside one session.
    """

    def resolve(self, query: str) -> CoverageLookupResult:
        """Free text -> candidate CPT codes. Plan-independent: the 20x4 grid is
        total, so every code exists for every plan."""
        raw = query or ""

        if m := _code_re().search(raw):
            code = m.group(1).upper()
            return CoverageLookupResult(
                resolution=Resolution.RESOLVED, matched_on=code, candidates=[code]
            )

        if m := _CODE_SHAPED.search(raw):
            return CoverageLookupResult(
                resolution=Resolution.UNKNOWN_CODE, matched_on=m.group(1).upper()
            )

        norm = normalize(raw)
        hits = [(p, codes) for p, codes in _phrase_index() if f" {p} " in norm]
        if hits:
            longest = len(hits[0][0])
            # Ties at the same length are unioned rather than arbitrarily picked.
            tied = [codes for p, codes in hits if len(p) == longest]
            matched = [p for p, _ in hits if len(p) == longest]
            codes = sorted({c for group in tied for c in group})
            resolution = Resolution.RESOLVED if len(codes) == 1 else Resolution.AMBIGUOUS
            return CoverageLookupResult(
                resolution=resolution, matched_on=", ".join(matched), candidates=codes
            )

        return CoverageLookupResult(
            resolution=Resolution.NOT_FOUND,
            suggestions=sorted(descriptions().values()),
        )

    def lookup(self, query: str, plan_type: str) -> CoverageLookupResult:
        """Resolve, then attach this plan's rules. Never guesses a plan."""
        if plan_type not in PLAN_TYPES:
            raise ValueError(f"unknown plan_type {plan_type!r}")
        result = self.resolve(query)
        result.rules = [self.rule_for(c, plan_type) for c in result.candidates]
        return result

    def rule_for(self, cpt_code: str, plan_type: str) -> CoverageRule:
        """O(1) and guaranteed present -- the grid is asserted total at load."""
        return rule_index()[(plan_type.upper(), cpt_code.upper())]

    def all_plans_for(self, cpt_code: str) -> list[CoverageRule]:
        """Same service across all 4 plans. Cheap because the grid is total."""
        return [self.rule_for(cpt_code, p) for p in PLAN_TYPES]


def rules_agree(rules: list[CoverageRule]) -> bool:
    """True when candidates are materially identical, so ambiguity is moot."""
    if len(rules) <= 1:
        return True
    facts = {(r.covered, r.prior_auth_required, r.copay, r.cost_share_pct) for r in rules}
    return len(facts) == 1


__all__ = ["BenefitsKB", "CsvBenefitsKB", "normalize", "all_codes", "rules_agree", "load_rules"]
