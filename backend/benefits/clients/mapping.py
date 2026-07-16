"""Row dict -> model, shared by every backend.

The two backends hand over different Python types for the same column: the CSV
reader yields the string "false", while BigQuery yields a real bool (often
numpy.bool_ once it has been through a DataFrame). Both must land on the same
model, so coercion lives here rather than in either client.

The bool case is the dangerous one: bool("false") is True, so a naive cast
silently inverts every negative flag in the dataset -- including `covered`.
"""

from typing import Any

from ..models import CoverageRule, Member, Provider

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0", ""}


def coerce_bool(value: Any) -> bool:
    """Accept CSV strings and BigQuery BOOLs alike; reject anything else."""
    if isinstance(value, bool):
        return value
    # numpy.bool_ and friends: duck-typed so numpy stays an optional import.
    if hasattr(value, "item") and not isinstance(value, str):
        return coerce_bool(value.item())
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"unparseable boolean: {value!r}")
    if value is None:
        return False
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
    raise ValueError(f"unparseable boolean: {value!r}")


def coerce_int(value: Any) -> int:
    """int64/Decimal/str -> int, without silently truncating a real fraction."""
    if value is None or value == "":
        return 0
    if hasattr(value, "item") and not isinstance(value, str):
        value = value.item()
    result = int(value)
    if isinstance(value, float) and value != result:
        raise ValueError(f"refusing to truncate {value!r}")
    return result


def coerce_str(value: Any) -> str:
    """BigQuery NULL and pandas NaN both mean empty here (only `notes` is nullable)."""
    if value is None:
        return ""
    if not isinstance(value, str) and value != value:  # NaN
        return ""
    return str(value)


def to_coverage_rule(row: dict[str, Any]) -> CoverageRule:
    return CoverageRule(
        rule_id=coerce_str(row["rule_id"]),
        plan_type=coerce_str(row["plan_type"]),
        cpt_code=coerce_str(row["cpt_code"]),
        cpt_description=coerce_str(row["cpt_description"]),
        covered=coerce_bool(row["covered"]),
        prior_auth_required=coerce_bool(row["prior_auth_required"]),
        cost_share_pct=coerce_int(row["cost_share_pct"]),
        copay=coerce_int(row["copay"]),
        notes=coerce_str(row["notes"]),
    )


def to_member(row: dict[str, Any]) -> Member:
    return Member(
        member_id=coerce_str(row["member_id"]),
        first_name=coerce_str(row["first_name"]),
        last_name=coerce_str(row["last_name"]),
        plan_type=coerce_str(row["plan_type"]),
        pcp_id=coerce_str(row["pcp_id"]),
        city=coerce_str(row["city"]),
        state=coerce_str(row["state"]),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        language_preference=coerce_str(row["language_preference"]),
    )


def to_provider(row: dict[str, Any]) -> Provider:
    return Provider(
        provider_id=coerce_str(row["provider_id"]),
        name=coerce_str(row["name"]),
        specialty=coerce_str(row["specialty"]),
        city=coerce_str(row["city"]),
        state=coerce_str(row["state"]),
        phone=coerce_str(row["phone"]),
        network_status=coerce_str(row["network_status"]),
        accepting_new_patients=coerce_bool(row["accepting_new_patients"]),
        hospital_affiliation=coerce_str(row["hospital_affiliation"]),
    )
