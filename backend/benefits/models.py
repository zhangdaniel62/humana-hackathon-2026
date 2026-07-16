"""Pydantic models for the Benefits Q&A agent."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def display_name(name: str) -> str:
    """providers.csv stores 'Dr. Last, First'; read it back as 'Dr. First Last'."""
    if ", " not in name:
        return name
    head, first = name.split(", ", 1)
    title, _, last = head.partition(" ")
    return f"{title} {first} {last}".strip() if last else f"{first} {head}".strip()


class Resolution(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    UNKNOWN_CODE = "unknown_code"


class CoverageRule(BaseModel):
    rule_id: str
    plan_type: str
    cpt_code: str
    cpt_description: str
    covered: bool
    prior_auth_required: bool
    cost_share_pct: int
    copay: int
    notes: str = ""

    @property
    def requires_in_network(self) -> bool:
        # notes == "Requires in-network provider" iff prior_auth_required, across
        # all 80 rows. Enforced by an invariant test; derived rather than re-read.
        return self.prior_auth_required


class Member(BaseModel):
    member_id: str
    first_name: str
    last_name: str
    plan_type: str
    pcp_id: str
    city: str
    state: str
    lat: float
    lon: float
    language_preference: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Provider(BaseModel):
    provider_id: str
    name: str
    specialty: str
    city: str
    state: str
    phone: str
    network_status: str
    accepting_new_patients: bool
    hospital_affiliation: str = ""

    @property
    def in_network(self) -> bool:
        return self.network_status == "In-Network"


class CoverageLookupResult(BaseModel):
    """Outcome of resolving a free-text service query to coverage rules."""

    resolution: Resolution
    matched_on: str = ""
    # populated when resolution is RESOLVED (len 1) or AMBIGUOUS (len >= 2)
    candidates: list[str] = Field(default_factory=list)  # cpt codes
    rules: list[CoverageRule] = Field(default_factory=list)
    # only for NOT_FOUND: the menu of services we can actually answer for
    suggestions: list[str] = Field(default_factory=list)

    @property
    def rule(self) -> CoverageRule | None:
        return self.rules[0] if self.resolution is Resolution.RESOLVED and self.rules else None


CostBasis = Literal[
    "not_covered",
    "no_cost",
    "copay_only",
    "coinsurance_only",
    "copay_plus_coinsurance",
]


class CostBreakdown(BaseModel):
    copay: int
    cost_share_pct: int
    basis: CostBasis
    estimate_text: str
    # We never fabricate a total: the allowed amount does not exist until the
    # claim is adjudicated. The explicit null is the point.
    dollar_total: None = None
    dollar_total_reason: str = (
        "The allowed amount is not known until the claim is adjudicated, "
        "so a single dollar total cannot be quoted."
    )


ProviderBasis = Literal[
    "specialty_in_state",
    "specialty_any",
    "secondary_specialty",
    "pcp_referral",
]

SpecialtyAvailability = Literal[
    "available",
    "none_accepting_new_patients",
    "not_in_network_directory",
]


class ProviderMatch(BaseModel):
    # Deliberately carries no distance field: the dataset's lat/lon do not agree
    # with city/state, so any mileage figure would be false precision.
    provider_id: str
    name: str
    specialty: str
    city: str
    state: str
    phone: str
    is_pcp: bool = False


class ProviderResult(BaseModel):
    providers: list[ProviderMatch] = Field(default_factory=list)
    basis: ProviderBasis
    specialty_requested: str | None = None
    specialty_availability: SpecialtyAvailability = "available"
    note: str = ""


class BenefitsAnswer(BaseModel):
    """The structured card handed to the UI.

    Every factual field is assembled deterministically from coverage_rules.csv.
    Only `answer_text` may be re-narrated by an LLM.
    """

    answer_text: str
    resolution: Resolution
    covered: bool | None = None
    prior_auth_required: bool | None = None
    cost: CostBreakdown | None = None
    next_step: str = ""
    providers: list[ProviderMatch] = Field(default_factory=list)
    grounded_on: list[str] = Field(default_factory=list)  # rule_ids
    #: Which backend served the coverage rules: csv | bigquery | csv_fallback.
    #: Part of the grounding story -- a fallback is reported, never silent.
    data_source: str = "csv"
    plan_type: str | None = None
    cpt_code: str | None = None
    language: str = "English"
    # populated when resolution is AMBIGUOUS so the UI can render choices
    choices: list[dict[str, str]] = Field(default_factory=list)
