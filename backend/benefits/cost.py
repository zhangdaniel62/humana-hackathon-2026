"""Cost presentation policy.

Two hard rules, both forced by the data:

1. Branch on `covered` FIRST. All 8 not-covered rows carry copay=0 and
   cost_share_pct=0, so any formatter that reads the money fields before
   checking coverage announces "your copay is $0" -- i.e. tells a DSNP member
   that a non-covered colonoscopy is free. That is the worst output this module
   could produce and it is one `if` away.

2. Never emit a dollar total. copay and coinsurance are both non-zero on 43 of
   80 rules, and the allowed amount does not exist until the claim is
   adjudicated, so no total is derivable. Say "and", never a formula -- the
   order of operations is an adjudication rule this dataset does not state.
"""

from .models import CoverageRule, CostBreakdown


def cost_breakdown(rule: CoverageRule) -> CostBreakdown:
    covered, copay, pct = rule.covered, rule.copay, rule.cost_share_pct

    if not covered:
        return CostBreakdown(
            copay=copay,
            cost_share_pct=pct,
            basis="not_covered",
            estimate_text=(
                f"{rule.cpt_description} is not covered under {rule.plan_type}. "
                "You would be responsible for the full billed amount."
            ),
        )

    if copay == 0 and pct == 0:
        basis, text = "no_cost", "This is fully covered - $0 to you."
    elif copay > 0 and pct == 0:
        basis, text = "copay_only", f"A ${copay} copay. No coinsurance."
    elif copay == 0 and pct > 0:
        basis, text = "coinsurance_only", f"No copay. You pay {pct}% of the allowed amount."
    else:
        basis, text = (
            "copay_plus_coinsurance",
            f"A ${copay} copay and {pct}% coinsurance of the allowed amount.",
        )

    return CostBreakdown(copay=copay, cost_share_pct=pct, basis=basis, estimate_text=text)
