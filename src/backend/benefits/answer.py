"""The deterministic 4-part answer. No LLM, no network, no ADK.

Coverage is a dict lookup, so narration is a presentation layer rather than a
reasoning layer. Everything a member needs -- covered, prior auth, cost, next
step -- is composed here from coverage_rules.csv alone. The ADK agent in
agent.py re-narrates `answer_text` and translates it; it adds no facts.

This inverts the usual cut order: the LLM is the most cuttable component in the
module, not the least. If Gemini is unavailable the demo still works.
"""

from .contract import roi_permits_detail
from .cost import cost_breakdown
from .kb import CsvBenefitsKB, rules_agree
from .loader import data_source, load_members
from .models import BenefitsAnswer, CoverageRule, Resolution, display_name
from .providers import find_provider

_KB = CsvBenefitsKB()


# Services the member is asked to choose between, rendered as "A or B".
def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} or {items[-1]}"


def _roi_refusal(language: str) -> BenefitsAnswer:
    return BenefitsAnswer(
        answer_text=(
            "I can't share this member's specific coverage or costs without a "
            "Release of Information on file for you. You can submit one in minutes "
            "at the member portal, or I can text you the link - then I can answer "
            "in full. I'm still happy to explain how this plan works in general."
        ),
        resolution=Resolution.NOT_FOUND,
        next_step="Submit a Release of Information via the member portal.",
        language=language,
    )


def _not_found(result, language: str) -> BenefitsAnswer:
    return BenefitsAnswer(
        answer_text=(
            "I don't have a coverage rule for that service, so I can't tell you "
            "whether it's covered - I won't guess. I can check any of these: "
            f"{', '.join(result.suggestions)}."
        ),
        resolution=Resolution.NOT_FOUND,
        next_step="Ask about one of the services listed, or I can transfer you to a benefits specialist.",
        language=language,
    )


def _unknown_code(result, language: str) -> BenefitsAnswer:
    return BenefitsAnswer(
        answer_text=(
            f"{result.matched_on} isn't a code in this plan's rule set, so I can't "
            "tell you how it's covered. I won't guess at a code I don't have."
        ),
        resolution=Resolution.UNKNOWN_CODE,
        next_step="Double-check the code with your provider's office, or describe the service in plain words.",
        language=language,
    )


def _ambiguous(result, language: str) -> BenefitsAnswer:
    names = [r.cpt_description for r in result.rules]
    return BenefitsAnswer(
        answer_text=(
            f"That could mean {_join(names)}, and they're covered differently "
            "under this plan - so I don't want to guess. Which one did you mean?"
        ),
        resolution=Resolution.AMBIGUOUS,
        next_step="Tell me which service you mean and I'll check it exactly.",
        choices=[
            {"cpt_code": r.cpt_code, "description": r.cpt_description} for r in result.rules
        ],
        grounded_on=[r.rule_id for r in result.rules],
        plan_type=result.rules[0].plan_type if result.rules else None,
        language=language,
    )


def _next_step(rule: CoverageRule, providers) -> str:
    if not rule.covered:
        return (
            "Ask your provider whether a covered alternative applies, or appeal if "
            "you believe this was billed under the wrong code."
        )
    if rule.prior_auth_required:
        return (
            "Ask your provider's office to submit the prior authorization request "
            "before scheduling - and confirm they're in-network."
        )
    return "You can schedule this with your provider; no prior authorization is needed."


def _compose(rule: CoverageRule, providers, cost) -> str:
    lines: list[str] = []

    if rule.covered:
        lines.append(f"{rule.cpt_description} is covered under your {rule.plan_type} plan.")
        # notes == "Requires in-network provider" iff prior_auth_required across all
        # 80 rows, so these are one condition and are stated as one sentence.
        if rule.prior_auth_required:
            lines.append("It needs prior authorization, and must be done by an in-network provider.")
        else:
            lines.append("It does not need prior authorization.")

    # For a non-covered service the cost text already names the service and the
    # plan, so a lead line would just repeat it.
    lines.append(cost.estimate_text)

    if providers and providers.note:
        lines.append(providers.note)
        lines.append(
            ", ".join(
                f"{display_name(p.name)} ({p.specialty}, {p.city}, {p.state}) {p.phone}"
                for p in providers.providers
            )
        )

    return " ".join(lines)


def answer_benefits_question(
    question: str,
    member_id: str | None = None,
    roi_status: str | None = "not_required",
    plan_type: str | None = None,
) -> BenefitsAnswer:
    """Answer a coverage question deterministically.

    `member_id` personalises the answer; `plan_type` alone answers generically.
    ROI fails closed: anything other than verified/not_required refuses detail.
    """
    member = load_members()[member_id] if member_id else None
    language = member.language_preference if member else "English"

    if member is not None and not roi_permits_detail(roi_status):
        return _roi_refusal(language)

    resolved_plan = plan_type or (member.plan_type if member else None)
    if resolved_plan is None:
        raise ValueError("need either member_id or plan_type")

    result = _KB.lookup(question, resolved_plan)

    if result.resolution is Resolution.NOT_FOUND:
        return _not_found(result, language)
    if result.resolution is Resolution.UNKNOWN_CODE:
        return _unknown_code(result, language)

    if result.resolution is Resolution.AMBIGUOUS and not rules_agree(result.rules):
        return _ambiguous(result, language)

    # Either a clean resolution, or candidates that happen to agree on every
    # material fact -- in which case the ambiguity doesn't change the answer.
    rule = result.rules[0]
    cost = cost_breakdown(rule)

    providers = None
    if rule.covered and rule.prior_auth_required and member is not None:
        providers = find_provider(rule.cpt_code, member.member_id)

    answer = BenefitsAnswer(
        answer_text=_compose(rule, providers, cost),
        resolution=Resolution.RESOLVED,
        covered=rule.covered,
        prior_auth_required=rule.prior_auth_required,
        cost=cost,
        next_step=_next_step(rule, providers),
        providers=providers.providers if providers else [],
        grounded_on=[r.rule_id for r in result.rules],
        data_source=data_source(),
        plan_type=rule.plan_type,
        cpt_code=rule.cpt_code,
        language=language,
    )
    return answer
