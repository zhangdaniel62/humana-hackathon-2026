"""Pure tests for the Benefits Q&A agent. No LLM, no network.

Expectations here are derived from the actual CSVs, not from intuition. Several
encode findings that contradict a plausible-sounding guess -- notably that
"knee surgery" is ambiguous rather than resolving to 27447, and that a
not-covered service must never be described as costing $0.
"""

import pytest

from backend.src.agents.benefits import (
    PLAN_TYPES,
    CsvBenefitsKB,
    Resolution,
    cost_breakdown,
    find_provider,
    load_members,
    load_providers,
    load_rules,
    parse_bool,
    roi_permits_detail,
)
from backend.src.agents.benefits import answer_benefits_question as ask

KB = CsvBenefitsKB()


def codes(query: str) -> set[str]:
    return set(KB.resolve(query).candidates)


def res(query: str) -> Resolution:
    return KB.resolve(query).resolution


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def test_exact_code():
    assert res("45378") is Resolution.RESOLVED
    assert codes("45378") == {"45378"}


def test_g0444_is_not_five_digits():
    """Regression: r'\\d{5}' silently misses G0444, one of the 8 not-covered rules."""
    assert res("G0444") is Resolution.RESOLVED
    assert codes("G0444") == {"G0444"}


def test_code_is_case_insensitive():
    assert codes("g0444") == {"G0444"}


def test_code_embedded_in_a_sentence():
    assert codes("is CPT 99213 covered") == {"99213"}


def test_knee_surgery_is_ambiguous():
    """Not 27447. Both knee procedures match, and they are priced differently."""
    assert res("knee surgery") is Resolution.AMBIGUOUS
    assert codes("knee surgery") == {"27447", "29881"}


def test_specific_alias_beats_the_broad_group():
    """'total knee replacement' contains 'knee'; specificity must still win."""
    assert res("total knee replacement") is Resolution.RESOLVED
    assert codes("total knee replacement") == {"27447"}


def test_depression_screening_is_ambiguous():
    assert codes("depression screening") == {"96127", "G0444"}


def test_blood_test_is_ambiguous_across_four():
    assert codes("blood test") == {"80053", "82962", "83036", "85025"}


def test_blood_glucose_test_is_not_the_blood_test_group():
    assert res("blood glucose test") is Resolution.RESOLVED
    assert codes("blood glucose test") == {"82962"}


def test_office_and_preventive_visits_are_ambiguous():
    assert codes("office visit") == {"99213", "99214"}
    assert codes("preventive visit") == {"99396", "99397"}


def test_colonoscopy_resolves():
    assert codes("colonoscopy") == {"45378"}


def test_code_shaped_but_unknown_never_resolves():
    assert res("12345") is Resolution.UNKNOWN_CODE
    assert codes("12345") == set()


def test_unknown_service_never_guesses():
    r = KB.resolve("liposuction")
    assert r.resolution is Resolution.NOT_FOUND
    assert r.candidates == []
    assert len(r.suggestions) == 20


# --------------------------------------------------------------------------
# Coverage: the plan differential
# --------------------------------------------------------------------------

def test_colonoscopy_differs_by_plan():
    assert KB.lookup("colonoscopy", "DSNP").rule.covered is False
    for plan in ("HMO", "MAPD", "PPO"):
        rule = KB.lookup("colonoscopy", plan).rule
        assert rule.covered is True
        assert rule.prior_auth_required is True


def test_ambiguity_is_a_correctness_issue_not_ux():
    """The load-bearing case: one colloquial phrase, opposite answers on DSNP."""
    assert KB.rule_for("96127", "DSNP").covered is True
    assert KB.rule_for("G0444", "DSNP").covered is False


def test_the_polarity_inverts_on_ppo():
    assert KB.rule_for("96127", "PPO").covered is False
    ppo_g0444 = KB.rule_for("G0444", "PPO")
    assert ppo_g0444.covered is True
    assert ppo_g0444.copay == 50


def test_grid_is_total():
    rules = load_rules()
    assert len(rules) == 80
    assert len({(r.plan_type, r.cpt_code) for r in rules}) == 80
    for plan in PLAN_TYPES:
        assert len({r.cpt_code for r in rules if r.plan_type == plan}) == 20


def test_not_covered_rows_carry_no_cost_fields():
    """All 8 not-covered rows are zeroed -- which is exactly why cost.py must
    branch on `covered` before reading them."""
    not_covered = [r for r in load_rules() if not r.covered]
    assert len(not_covered) == 8
    for r in not_covered:
        assert r.prior_auth_required is False
        assert r.cost_share_pct == 0 and r.copay == 0


def test_notes_iff_prior_auth():
    """If this breaks, the merged 'prior auth + in-network' sentence is wrong."""
    rules = load_rules()
    assert sum(r.prior_auth_required for r in rules) == 19
    for r in rules:
        assert (r.notes == "Requires in-network provider") == r.prior_auth_required


def test_parse_bool_rejects_the_classic_cast():
    """bool('false') is True -- which would invert every negative flag loaded."""
    assert parse_bool("false") is False
    assert parse_bool("true") is True
    assert bool("false") is True  # the bug being guarded against
    with pytest.raises(ValueError):
        parse_bool("maybe")


# --------------------------------------------------------------------------
# Cost
# --------------------------------------------------------------------------

def test_not_covered_is_never_described_as_free():
    """Highest-value test here: a DSNP colonoscopy is not covered, and all its
    money fields are 0. Saying '$0' would tell the member it is free."""
    text = cost_breakdown(KB.rule_for("45378", "DSNP")).estimate_text
    assert "$0" not in text
    assert "no cost" not in text.lower()
    assert "not covered" in text.lower()
    assert "full billed amount" in text.lower()


def test_copay_plus_coinsurance_states_both():
    rule = KB.rule_for("99213", "HMO")  # copay 20, pct 20
    cb = cost_breakdown(rule)
    assert cb.basis == "copay_plus_coinsurance"
    assert "$20" in cb.estimate_text and "20%" in cb.estimate_text


def test_coinsurance_only():
    cb = cost_breakdown(KB.rule_for("45378", "MAPD"))  # copay 0, pct 20
    assert cb.basis == "coinsurance_only"
    assert "20%" in cb.estimate_text


def test_no_total_is_ever_fabricated():
    for rule in load_rules():
        assert cost_breakdown(rule).dollar_total is None


def test_every_rule_has_a_cost_basis():
    for rule in load_rules():
        assert cost_breakdown(rule).basis


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

def test_zero_gastro_falls_back_to_the_pcp():
    r = find_provider("colonoscopy", "MBR00183")
    assert r.basis == "pcp_referral"
    assert r.specialty_availability == "none_accepting_new_patients"
    assert r.providers and r.providers[0].is_pcp


def test_psychotherapy_finds_psychiatry():
    r = find_provider("psychotherapy", "MBR00183")
    assert r.specialty_requested == "Psychiatry"
    assert r.providers


def test_find_provider_never_empty_and_never_raises():
    """200 members x 20 CPTs. The guarantee rests on every member having an
    in-network PCP."""
    members = list(load_members())
    all_codes = sorted({r.cpt_code for r in load_rules()})
    for member_id in members:
        for code in all_codes:
            r = find_provider(code, member_id)
            assert r.providers, f"empty for {member_id}/{code}"


def test_suggested_providers_are_in_network():
    for member_id in list(load_members())[:25]:
        for code in ("45378", "70553", "93000", "90837", "99213"):
            for p in find_provider(code, member_id).providers:
                assert load_providers()[p.provider_id].in_network


def test_no_mileage_is_ever_quoted():
    """lat/lon disagree with city/state and the median nearest provider is 217
    miles away, so any distance figure would be false precision."""
    blob = find_provider("colonoscopy", "MBR00183").model_dump_json().lower()
    for token in ("mile", "distance", "km", "away"):
        assert token not in blob


# --------------------------------------------------------------------------
# ROI: fail closed
# --------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["verified", "not_required"])
def test_roi_allows_detail(status):
    assert roi_permits_detail(status) is True
    a = ask("colonoscopy", member_id="MBR00183", roi_status=status)
    assert a.covered is True
    assert a.grounded_on == ["RULE0070"]


@pytest.mark.parametrize("status", ["missing", "expired", None, "", "VERIFIED", "unknown"])
def test_roi_fails_closed(status):
    """'expired' is 43 rows in the data and must not fall through as verified."""
    assert roi_permits_detail(status) is False
    a = ask("colonoscopy", member_id="MBR00183", roi_status=status)
    assert a.covered is None
    assert a.cost is None
    assert "Release of Information" in a.answer_text


# --------------------------------------------------------------------------
# End-to-end answer, deterministic
# --------------------------------------------------------------------------

def test_golden_path_is_grounded_on_the_csv_row():
    a = ask("what would a colonoscopy cost me", member_id="MBR00183")
    rule = KB.rule_for("45378", "MAPD")
    assert a.grounded_on == ["RULE0070"]
    assert a.plan_type == "MAPD"
    assert a.covered is rule.covered
    assert a.prior_auth_required is rule.prior_auth_required
    assert a.cost.copay == rule.copay
    assert a.cost.cost_share_pct == rule.cost_share_pct
    assert a.language == "Spanish"
    assert a.providers[0].is_pcp


def test_ambiguous_question_asks_rather_than_answers():
    a = ask("is depression screening covered", member_id="MBR00125")  # DSNP
    assert a.resolution is Resolution.AMBIGUOUS
    assert a.covered is None
    assert len(a.choices) == 2
    assert "which one" in a.answer_text.lower()


def test_unknown_service_declines():
    a = ask("is acupuncture covered", member_id="MBR00183")
    assert a.resolution is Resolution.NOT_FOUND
    assert a.covered is None
    assert "won't guess" in a.answer_text


def test_answer_is_deterministic():
    first = ask("colonoscopy", member_id="MBR00183")
    for _ in range(3):
        assert ask("colonoscopy", member_id="MBR00183") == first


# --------------------------------------------------------------------------
# ADK marshalling layer
#
# The tools only touch `tool_context.state`, so a stub exercises the real code
# path without standing up a session or an LLM.
# --------------------------------------------------------------------------

class StubContext:
    def __init__(self, **state):
        self.state = dict(state)


@pytest.fixture(autouse=True)
def _clear_events():
    from backend.src.agents.benefits import EVENT_LOG

    EVENT_LOG.clear()
    yield
    EVENT_LOG.clear()


def test_tool_grounds_and_records_to_state():
    from backend.src.agents.benefits import AGENT_KEY, StateKeys, lookup_coverage

    ctx = StubContext(subject_member_id="MBR00183", roi_status="verified", session_id="S1")
    out = lookup_coverage("what would a colonoscopy cost me", ctx)

    assert out["status"] == "ok"
    assert out["grounded_on"] == ["RULE0070"]
    assert out["cost"]["dollar_total"] is None
    # the card is assembled from state, not parsed back out of the model's prose
    assert ctx.state[StateKeys.LAST_LOOKUP]["grounded_on"] == ["RULE0070"]
    assert ctx.state[StateKeys.AGENT_FINDINGS][AGENT_KEY]["cpt_code"] == "45378"


def test_tool_emits_coverage_event():
    from backend.src.agents.benefits import EVENT_LOG, EVENT_TYPE, lookup_coverage

    lookup_coverage("colonoscopy", StubContext(subject_member_id="MBR00183", session_id="S1"))
    event = next(e for e in EVENT_LOG if e["event_type"] == EVENT_TYPE)
    assert event["cpt_code"] == "45378"
    assert event["matched_rule_id"] == "RULE0070"
    assert event["answered_in_language"] == "Spanish"
    assert event["match_type"] == "resolved"


def test_tool_refuses_without_roi_and_leaks_nothing():
    from backend.src.agents.benefits import lookup_coverage

    ctx = StubContext(subject_member_id="MBR00183", roi_status="expired")
    out = lookup_coverage("colonoscopy", ctx)
    assert out["status"] == "roi_required"
    assert "covered" not in out
    blob = str(out).lower()
    assert "mapd" not in blob and "rule0070" not in blob


def test_tool_requires_a_member():
    from backend.src.agents.benefits import lookup_coverage

    assert lookup_coverage("colonoscopy", StubContext())["status"] == "no_member"


def test_network_gap_event_is_emitted_for_zero_gastro():
    """A specialty in-network with nobody accepting new patients is a
    network-adequacy finding -- it feeds Sentinel's dashboard."""
    from backend.src.agents.benefits import EVENT_LOG, NETWORK_GAP_EVENT, find_provider_tool

    out = find_provider_tool("colonoscopy", StubContext(subject_member_id="MBR00183"))
    assert out["basis"] == "pcp_referral"
    event = next(e for e in EVENT_LOG if e["event_type"] == NETWORK_GAP_EVENT)
    assert event["specialty"] == "Gastroenterology"
    assert event["member_state"] == "DE"
