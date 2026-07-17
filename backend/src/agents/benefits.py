import csv
import logging
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    import pandas as pd
    from google.adk.agents import LlmAgent

try:
    # Imported eagerly, but optionally: ADK resolves a tool's parameter
    # annotations at runtime to build its function declaration, so `ToolContext`
    # must be a real name in this module's namespace when ADK is installed. When
    # it isn't, the deterministic core below must still import.
    from google.adk.tools import ToolContext
except ImportError:  # pragma: no cover - exercised only without the ADK extra
    ToolContext = Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# contract -- integration seam
#
# The orchestrator and UI depend on these symbols. No logic, no dependencies.
# ---------------------------------------------------------------------------


class StateKeys:
    """Keys the Benefits agent reads from / writes to ADK session state."""

    # read
    SUBJECT_MEMBER_ID: Final = "subject_member_id"
    ROI_STATUS: Final = "roi_status"
    CALLER_NAME: Final = "caller_name"
    SESSION_ID: Final = "session_id"

    # write
    AGENT_FINDINGS: Final = "agent_findings"  # -> [...][AGENT_KEY]

    # internal to this agent; the deterministic card is built from this
    LAST_LOOKUP: Final = "benefits:last_lookup"


AGENT_KEY: Final = "benefits_qa"

EVENT_TYPE: Final = "coverage_question_answered"
NETWORK_GAP_EVENT: Final = "network_gap_detected"

# ROI states that permit member-specific coverage detail. Anything else --
# "missing", "expired", None, or an unrecognised value -- fails closed.
ROI_ALLOWED: Final = frozenset({"verified", "not_required"})

PLAN_TYPES: Final = ("DSNP", "HMO", "MAPD", "PPO")


def roi_permits_detail(roi_status: str | None) -> bool:
    """Fail closed: only explicitly allowed statuses unlock member detail."""
    return roi_status in ROI_ALLOWED


# ---------------------------------------------------------------------------
# events -- compatibility view over the shared application EventLog
#
# Fire-and-forget; never in the request path. Sentinel consumes the shared typed
# stream; the view preserves the legacy list-style test seam without duplicating
# storage.
# ---------------------------------------------------------------------------

class _LegacyEventView:
    """List-like test compatibility without creating a second event store."""

    def __init__(self) -> None:
        self._start_index = 0

    def __iter__(self):
        from ..events import event_log

        for typed_event in event_log.events[self._start_index :]:
            if typed_event.agent != "benefits_qa":
                continue
            yield {
                "timestamp": typed_event.timestamp.isoformat(),
                "agent": typed_event.agent,
                "event_type": typed_event.event_type.value,
                "session_id": typed_event.session_id,
                "member_id": typed_event.member_id,
                "claim_id": typed_event.claim_id,
                **typed_event.payload,
            }

    def clear(self) -> None:
        from ..events import event_log

        self._start_index = len(event_log.events)


EVENT_LOG = _LegacyEventView()


def emit(event_type: str, payload: dict[str, Any], *, agent: str = "benefits_qa") -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": agent,
        "event_type": event_type,
        **payload,
    }
    from ..events import event_log
    from ..models import AgentEvent, EventType

    typed_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"session_id", "member_id", "claim_id"}
        and value is not None
    }
    event_log.publish_nowait(
        AgentEvent(
            session_id=str(payload.get("session_id") or "unknown"),
            agent=agent,
            event_type=EventType(event_type),
            member_id=payload.get("member_id"),
            claim_id=payload.get("claim_id"),
            payload=typed_payload,
        )
    )
    return event


def drain() -> list[dict[str, Any]]:
    events = list(EVENT_LOG)
    EVENT_LOG.clear()
    return events


# ---------------------------------------------------------------------------
# settings -- single BaseSettings, singleton instance, injectable for tests
# ---------------------------------------------------------------------------

DataSource = Literal["csv", "bigquery"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BENEFITS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Where coverage_rules / members / providers come from. CSV is the default
    #: because it needs no credentials and cannot fail on demo day.
    data_source: DataSource = "csv"

    #: When data_source is "bigquery" and BigQuery is unreachable, fall back to
    #: the CSVs rather than failing the request. The CSVs are the same data, so
    #: the answer stays correct; the source actually used is reported on every
    #: answer via BenefitsAnswer.data_source. Set False to fail loudly instead.
    bigquery_fallback_to_csv: bool = True

    bq_project: str | None = None
    bq_dataset: str | None = None
    bq_location: str | None = None

    #: Table names, in case they differ from the CSV basenames.
    bq_coverage_rules_table: str = "coverage_rules"
    bq_members_table: str = "members"
    bq_providers_table: str = "providers"

    datasets_dir: Path = Field(default=_REPO_ROOT / "datasets")

    model: str = "gemini-flash-latest"

    @model_validator(mode="after")
    def _require_bq_config(self) -> "Settings":
        if self.data_source == "bigquery" and not (self.bq_project and self.bq_dataset):
            raise ValueError(
                "data_source='bigquery' requires BENEFITS_BQ_PROJECT and "
                "BENEFITS_BQ_DATASET to be set."
            )
        return self

    def table_ref(self, table: str) -> str:
        return f"{self.bq_project}.{self.bq_dataset}.{table}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton. Pass an explicit Settings to inject in tests."""
    return Settings()


def reset_settings_cache() -> None:
    """For tests that mutate the environment."""
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# mapping -- row dict -> model, shared by every backend
#
# The two backends hand over different Python types for the same column: the CSV
# reader yields the string "false", while BigQuery yields a real bool (often
# numpy.bool_ once it has been through a DataFrame). Both must land on the same
# model, so coercion lives here rather than in either client.
#
# The bool case is the dangerous one: bool("false") is True, so a naive cast
# silently inverts every negative flag in the dataset -- including `covered`.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# protocols -- one per table the Benefits agent reads
#
# Implementations must return the same model objects regardless of backend, so
# everything above this layer -- kb, providers, answer -- is backend-agnostic and
# never sees a DataFrame.
#
# claims.csv is deliberately absent: it belongs to the Claim Story agent, and it
# disagrees with coverage_rules on prior-auth for 50 of 880 rows, so this module
# must never read it.
# ---------------------------------------------------------------------------


@runtime_checkable
class CoverageRulesClient(Protocol):
    #: Which backend actually served the data ("csv", "bigquery", "csv_fallback").
    source: str

    def fetch_all(self) -> tuple[CoverageRule, ...]: ...


@runtime_checkable
class MemberRecordsClient(Protocol):
    source: str

    def fetch_all(self) -> dict[str, Member]: ...


@runtime_checkable
class ProviderDirectoryClient(Protocol):
    source: str

    def fetch_all(self) -> dict[str, Provider]: ...


# ---------------------------------------------------------------------------
# csv clients -- stdlib only: no pandas, no network, no credentials
#
# This is the fallback path, so it deliberately depends on nothing that can fail
# to install or time out. It is also the default.
# ---------------------------------------------------------------------------


class _CsvClient:
    filename: str

    def __init__(self, settings: Settings | None = None, source: str = "csv") -> None:
        self.settings = settings or get_settings()
        self.source = source

    @property
    def path(self) -> Path:
        return Path(self.settings.datasets_dir) / self.filename

    def _rows(self) -> list[dict[str, Any]]:
        with self.path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))


class CsvCoverageRulesClient(_CsvClient):
    filename = "coverage_rules.csv"

    def fetch_all(self) -> tuple[CoverageRule, ...]:
        return tuple(to_coverage_rule(r) for r in self._rows())


class CsvMemberRecordsClient(_CsvClient):
    filename = "members.csv"

    def fetch_all(self) -> dict[str, Member]:
        members = (to_member(r) for r in self._rows())
        return {m.member_id: m for m in members}


class CsvProviderDirectoryClient(_CsvClient):
    filename = "providers.csv"

    def fetch_all(self) -> dict[str, Provider]:
        providers = (to_provider(r) for r in self._rows())
        return {p.provider_id: p for p in providers}


# ---------------------------------------------------------------------------
# bigquery clients
#
# Each client pulls its whole table into a DataFrame once, at construction. That
# is appropriate here and not a shortcut: the three tables are 80, 200 and 50
# rows, so the entire dataset is a few hundred rows. Loading eagerly buys
# per-query latency of zero, no round-trip inside the request path, and no
# partial-failure states mid-conversation.
#
# pandas and google-cloud-bigquery are an optional extra (`.[bigquery]`) and are
# imported lazily inside `_client`, so a machine without them -- or with a broken
# install -- falls back to CSV instead of failing to import.
# ---------------------------------------------------------------------------


class BigQueryUnavailable(RuntimeError):
    """BigQuery could not serve this table: bad config, creds, network, or extra."""


class _BigQueryClient:
    """Loads one table into a DataFrame at init."""

    table_setting: str

    def __init__(self, settings: Settings | None = None, bq_client: Any = None) -> None:
        self.settings = settings or get_settings()
        self.source = "bigquery"
        self._bq = bq_client
        self.df = self._load_dataframe()

    @property
    def table(self) -> str:
        return self.settings.table_ref(getattr(self.settings, self.table_setting))

    def _client(self) -> Any:
        if self._bq is not None:
            return self._bq
        try:
            from google.cloud import bigquery
        except ImportError as exc:  # extra not installed
            raise BigQueryUnavailable(
                "google-cloud-bigquery is not installed. Install the extra: "
                "uv sync --extra bigquery"
            ) from exc
        return bigquery.Client(
            project=self.settings.bq_project, location=self.settings.bq_location
        )

    def _load_dataframe(self) -> "pd.DataFrame":
        try:
            client = self._client()
            df = client.query(f"SELECT * FROM `{self.table}`").to_dataframe()
        except BigQueryUnavailable:
            raise
        except Exception as exc:
            raise BigQueryUnavailable(f"could not load {self.table}: {exc}") from exc

        if df.empty:
            # An empty table is a config error pointing at the wrong place, not a
            # dataset with no rows. Failing here lets the factory fall back.
            raise BigQueryUnavailable(f"{self.table} returned zero rows")

        log.info("loaded %s rows from %s", len(df), self.table)
        return df

    def _records(self) -> list[dict[str, Any]]:
        return self.df.to_dict("records")


class BigQueryCoverageRulesClient(_BigQueryClient):
    table_setting = "bq_coverage_rules_table"

    def fetch_all(self) -> tuple[CoverageRule, ...]:
        return tuple(to_coverage_rule(r) for r in self._records())


class BigQueryMemberRecordsClient(_BigQueryClient):
    table_setting = "bq_members_table"

    def fetch_all(self) -> dict[str, Member]:
        members = (to_member(r) for r in self._records())
        return {m.member_id: m for m in members}


class BigQueryProviderDirectoryClient(_BigQueryClient):
    table_setting = "bq_providers_table"

    def fetch_all(self) -> dict[str, Provider]:
        providers = (to_provider(r) for r in self._records())
        return {p.provider_id: p for p in providers}


# ---------------------------------------------------------------------------
# client factory -- the settings toggle and the BigQuery -> CSV fallback
#
# Fallback is per-table and happens at construction, so a session can never start
# against BigQuery and then silently change source mid-conversation.
#
# The fallback is safe precisely because the CSVs hold the same data, so an
# answer is equally grounded either way -- but it is never silent: it logs a
# warning and the source actually used is reported on every answer as
# `BenefitsAnswer.data_source`.
# ---------------------------------------------------------------------------

FALLBACK_SOURCE = "csv_fallback"

_CSV = {
    "coverage_rules": CsvCoverageRulesClient,
    "members": CsvMemberRecordsClient,
    "providers": CsvProviderDirectoryClient,
}

_BIGQUERY = {
    "coverage_rules": BigQueryCoverageRulesClient,
    "members": BigQueryMemberRecordsClient,
    "providers": BigQueryProviderDirectoryClient,
}


def _build(kind: str, settings: Settings):
    if settings.data_source != "bigquery":
        return _CSV[kind](settings=settings)

    try:
        return _BIGQUERY[kind](settings=settings)
    except Exception as exc:
        if not settings.bigquery_fallback_to_csv:
            raise
        log.warning(
            "BigQuery unavailable for %s (%s); falling back to CSV. "
            "Answers stay grounded in the same data, but the source is now CSV.",
            kind,
            exc,
        )
        return _CSV[kind](settings=settings, source=FALLBACK_SOURCE)


def get_coverage_rules_client(settings: Settings | None = None) -> CoverageRulesClient:
    return _build("coverage_rules", settings or get_settings())


def get_member_records_client(settings: Settings | None = None) -> MemberRecordsClient:
    return _build("members", settings or get_settings())


def get_provider_directory_client(settings: Settings | None = None) -> ProviderDirectoryClient:
    return _build("providers", settings or get_settings())


# ---------------------------------------------------------------------------
# loader -- facade over the data clients
#
# Everything above this section (kb, providers, answer) calls these functions and
# is unaware of whether the rows came from CSV or BigQuery. Swapping the backend
# touches only `settings.data_source`.
#
# Loaded once per process and cached: the whole dataset is ~330 rows.
# ---------------------------------------------------------------------------

# `parse_bool` predates the client layer and is still the clearest name at call
# sites; coerce_bool is the same function generalised to BigQuery's native types.
parse_bool = coerce_bool

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


# ---------------------------------------------------------------------------
# aliases -- hand-authored language maps over the 20 CPT codes
#
# Why hand-authored rather than fuzzy matching: the code set is tiny (20),
# closed, and known at author time. Fuzzy scoring over 20 items has no ground
# truth to tune against -- at any cutoff loose enough to catch real paraphrases,
# difflib matches "colonoscopy" to "Total Knee Arthroplasty". A map is
# deterministic, reviewable, dependency-free, and -- decisively -- lets ambiguity
# be *declared* rather than discovered by a threshold.
#
# ALIASES resolve to exactly one code. AMBIGUITY_GROUPS are colloquial phrases
# that genuinely name more than one service; they are answered with a question,
# never a guess. Canonical CSV descriptions are added to the index automatically
# by the kb section below.
# ---------------------------------------------------------------------------

# phrase -> single CPT code
ALIASES: dict[str, tuple[str, ...]] = {
    "27447": ("total knee replacement", "total knee arthroplasty", "knee replacement", "tka"),
    "29881": (
        "knee arthroscopy", "knee scope", "meniscectomy", "meniscus surgery",
        "torn meniscus", "arthroscopy with meniscectomy",
    ),
    "43239": (
        "upper gi endoscopy", "upper gi", "endoscopy with biopsy", "egd",
        "stomach scope", "gi biopsy", "endoscopy",
    ),
    "45378": ("colonoscopy", "colon screening", "colon cancer screening", "diagnostic colonoscopy"),
    "70553": (
        "mri brain", "brain mri", "mri with contrast", "brain scan",
        "head mri", "mri of the brain", "mri",
    ),
    "77067": ("mammogram", "mammography", "breast screening", "breast cancer screening"),
    "80053": ("comprehensive metabolic panel", "metabolic panel", "cmp", "chem panel"),
    "82962": ("blood glucose", "glucose test", "blood sugar", "sugar test", "glucose"),
    "83036": ("hemoglobin a1c", "a1c", "hba1c", "diabetes test", "diabetes blood test"),
    "85025": ("complete blood count", "cbc", "blood count"),
    "90837": ("psychotherapy", "therapy session", "talk therapy", "counseling", "counselling"),
    "93000": ("electrocardiogram", "ecg", "ekg", "heart tracing", "heart test"),
    "96127": ("depression screen", "brief depression screening"),
    "99091": (
        "remote patient monitoring", "remote monitoring", "rpm",
        "data analysis", "remote data review",
    ),
    "99213": ("level 3 office visit", "level 3 visit", "follow up visit", "follow-up visit"),
    "99214": ("level 4 office visit", "level 4 visit"),
    "99396": ("preventive visit age 40", "preventive visit 40-64", "adult physical"),
    "99397": (
        "preventive visit age 65", "preventive visit 65+", "senior physical",
        "medicare wellness visit",
    ),
    "99490": ("chronic care management", "chronic care", "care management", "ccm"),
    "G0444": ("annual depression screening", "medicare depression screening"),
}

# Colloquial phrases that genuinely name more than one service.
#
# The load-bearing one is "depression screening": for a DSNP member 96127 is
# COVERED and G0444 is NOT, and the polarity inverts on PPO. Silently picking one
# is a coin flip on telling a member a non-covered service is free. This is a
# correctness path, not a UX nicety.
AMBIGUITY_GROUPS: dict[str, tuple[str, ...]] = {
    "knee": ("27447", "29881"),
    "knee surgery": ("27447", "29881"),
    "knee operation": ("27447", "29881"),
    "depression screening": ("96127", "G0444"),
    "screening for depression": ("96127", "G0444"),
    "depression test": ("96127", "G0444"),
    "blood test": ("80053", "82962", "83036", "85025"),
    "blood work": ("80053", "82962", "83036", "85025"),
    "bloodwork": ("80053", "82962", "83036", "85025"),
    "labs": ("80053", "82962", "83036", "85025"),
    "lab work": ("80053", "82962", "83036", "85025"),
    "office visit": ("99213", "99214"),
    "doctor visit": ("99213", "99214"),
    "preventive visit": ("99396", "99397"),
    "annual visit": ("99396", "99397"),
    "wellness visit": ("99396", "99397"),
    "annual physical": ("99396", "99397"),
    "physical": ("99396", "99397"),
    "checkup": ("99396", "99397"),
    "scope": ("43239", "45378"),
}

# CPT -> ordered specialty preference. An empty tuple means no specialist is the
# right answer (labs/imaging/office visits are ordered by the member's own PCP).
#
# Gastroenterology and Oncology have ZERO in-network providers accepting new
# patients, so 43239/45378 always fall through to the PCP -- which is also the
# clinically correct first step, since a colonoscopy needs a PCP referral anyway.
CPT_SPECIALTY: dict[str, tuple[str, ...]] = {
    "27447": ("Orthopedics",),
    "29881": ("Orthopedics",),
    "43239": ("Gastroenterology",),
    "45378": ("Gastroenterology",),
    "70553": (),  # no Radiology in the directory; the PCP orders imaging
    "77067": ("OB/GYN",),
    "80053": ("Internal Medicine", "Family Medicine"),
    "82962": ("Internal Medicine", "Family Medicine"),
    "83036": ("Endocrinology", "Internal Medicine"),
    "85025": ("Internal Medicine", "Family Medicine"),
    "90837": ("Psychiatry",),
    "93000": ("Cardiology",),
    "96127": ("Psychiatry", "Internal Medicine"),
    "99091": ("Internal Medicine", "Family Medicine"),
    "99213": (),
    "99214": (),
    "99396": ("Internal Medicine", "Family Medicine"),
    "99397": ("Geriatrics", "Internal Medicine"),
    "99490": ("Internal Medicine", "Family Medicine"),
    "G0444": ("Internal Medicine", "Family Medicine"),
}


# ---------------------------------------------------------------------------
# kb -- resolve free-text service queries to coverage rules. No LLM, no network.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# cost -- presentation policy
#
# Two hard rules, both forced by the data:
#
# 1. Branch on `covered` FIRST. All 8 not-covered rows carry copay=0 and
#    cost_share_pct=0, so any formatter that reads the money fields before
#    checking coverage announces "your copay is $0" -- i.e. tells a DSNP member
#    that a non-covered colonoscopy is free. That is the worst output this
#    section could produce and it is one `if` away.
#
# 2. Never emit a dollar total. copay and coinsurance are both non-zero on 43 of
#    80 rules, and the allowed amount does not exist until the claim is
#    adjudicated, so no total is derivable. Say "and", never a formula -- the
#    order of operations is an adjudication rule this dataset does not state.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# providers -- suggestions. Pure; no ADK, no network, no distance.
#
# Two data facts drive this section:
#
# * Gastroenterology and Oncology have ZERO in-network providers accepting new
#   patients, so a colonoscopy question -- a flagship demo path -- returns
#   nothing under naive filtering. The fallback is the member's PCP, which is
#   also the clinically correct answer: a colonoscopy needs a PCP referral
#   anyway.
#
# * lat/lon do not agree with city/state and the median nearest eligible provider
#   is 217 miles away. Ranking or quoting mileage off that signal is false
#   precision, so this section computes no distances at all.
# ---------------------------------------------------------------------------

_LIMIT = 3


def _match(p: Provider, *, is_pcp: bool = False) -> ProviderMatch:
    return ProviderMatch(
        provider_id=p.provider_id,
        name=p.name,
        specialty=p.specialty,
        city=p.city,
        state=p.state,
        phone=p.phone,
        is_pcp=is_pcp,
    )


def _rank(providers: list[Provider], member: Member) -> list[Provider]:
    """Same state, then same city, then provider_id. Deterministic, no geo math."""
    return sorted(
        providers,
        key=lambda p: (
            p.state != member.state,
            p.city != member.city,
            p.provider_id,
        ),
    )


def _eligible(specialty: str) -> list[Provider]:
    return [
        p
        for p in load_providers().values()
        if p.specialty == specialty and p.in_network and p.accepting_new_patients
    ]


def _in_network(specialty: str) -> list[Provider]:
    return [p for p in load_providers().values() if p.specialty == specialty and p.in_network]


def _availability(specialty: str) -> str:
    if _eligible(specialty):
        return "available"
    if _in_network(specialty):
        return "none_accepting_new_patients"
    return "not_in_network_directory"


def _pcp_result(
    member: Member,
    specialty_requested: str | None,
    availability: str,
) -> ProviderResult:
    """Terminal fallback. Cannot be empty: all 200 members have an in-network PCP."""
    pcp = load_providers()[member.pcp_id]
    pcp_name = display_name(pcp.name)

    if specialty_requested is None:
        note = f"Your PCP, {pcp_name}, orders this for you - no specialist referral needed."
    elif availability == "none_accepting_new_patients":
        note = (
            f"No in-network {specialty_requested} providers are currently accepting "
            f"new patients. Your PCP, {pcp_name}, can refer you - which is the "
            f"required first step for this service regardless."
        )
    else:
        note = (
            f"There are no in-network {specialty_requested} providers in the "
            f"directory. Start with your PCP, {pcp_name}, for a referral."
        )

    return ProviderResult(
        providers=[_match(pcp, is_pcp=True)],
        basis="pcp_referral",
        specialty_requested=specialty_requested,
        specialty_availability=availability,
        note=note,
    )


def find_provider(service_or_specialty: str, member_id: str, limit: int = _LIMIT) -> ProviderResult:
    """Suggest providers for a service. Never returns an empty list.

    Walks the CPT's ordered specialty preference: same-state eligible, then
    any-state eligible, then the next specialty, then the member's PCP.
    """
    member = load_members()[member_id]

    specialties = _specialties_for(service_or_specialty)
    if not specialties:
        return _pcp_result(member, None, "available")

    primary = specialties[0]
    for index, specialty in enumerate(specialties):
        pool = _eligible(specialty)
        if not pool:
            continue

        ranked = _rank(pool, member)[:limit]
        in_state = [p for p in ranked if p.state == member.state]
        if index > 0:
            basis = "secondary_specialty"
        elif in_state:
            basis = "specialty_in_state"
        else:
            basis = "specialty_any"

        note = f"In-network {specialty} providers accepting new patients."
        if index > 0:
            note = (
                f"No in-network {primary} providers are accepting new patients; "
                f"these {specialty} providers can help."
            )

        return ProviderResult(
            providers=[_match(p) for p in ranked],
            basis=basis,
            specialty_requested=primary,
            specialty_availability="available",
            note=note,
        )

    return _pcp_result(member, primary, _availability(primary))


def _specialties_for(service_or_specialty: str) -> tuple[str, ...]:
    """Accept a CPT code, a free-text service, or a specialty name."""
    known = {p.specialty for p in load_providers().values()}
    for s in known:
        if s.lower() == service_or_specialty.strip().lower():
            return (s,)

    resolved = CsvBenefitsKB().resolve(service_or_specialty)
    if resolved.resolution is Resolution.RESOLVED:
        return CPT_SPECIALTY[resolved.candidates[0]]
    if resolved.resolution is Resolution.AMBIGUOUS:
        # Union the candidates' specialties, preserving preference order.
        ordered: list[str] = []
        for code in resolved.candidates:
            for s in CPT_SPECIALTY[code]:
                if s not in ordered:
                    ordered.append(s)
        return tuple(ordered)
    return ()


# ---------------------------------------------------------------------------
# answer -- the deterministic 4-part answer. No LLM, no network, no ADK.
#
# Coverage is a dict lookup, so narration is a presentation layer rather than a
# reasoning layer. Everything a member needs -- covered, prior auth, cost, next
# step -- is composed here from coverage_rules.csv alone. The ADK agent at the
# bottom of this module re-narrates `answer_text` and translates it; it adds no
# facts.
#
# This inverts the usual cut order: the LLM is the most cuttable component in the
# module, not the least. If Gemini is unavailable the demo still works.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# prompts
#
# The tool returns a complete, correct answer already. The model's job is
# narration and translation only -- so the prompt is written to constrain, not to
# reason.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a health-plan benefits assistant for members and call-center \
representatives.

HOW YOU WORK
- ALWAYS call `lookup_coverage` before answering any coverage, prior-authorization,
  or cost question. Never answer from your own knowledge of insurance.
- `lookup_coverage` returns an authoritative answer drawn from the plan's coverage
  rules, including a ready-made `answer_text`. Your job is to deliver that answer
  naturally - not to re-derive, second-guess, or add to it.
- Never state a coverage fact, a prior-auth requirement, a dollar amount, or a
  percentage that did not come from the tool.

WHAT EVERY ANSWER MUST CONTAIN
1. Whether it is covered.
2. Whether prior authorization is needed.
3. The expected cost.
4. One concrete next step.

COST - STRICT
- Report `copay` and `cost_share_pct` exactly as returned.
- NEVER add them together, estimate a total, or convert a percentage into dollars.
  The allowed amount is unknown until the claim is adjudicated. If asked for a
  total, explain that.
- If the service is NOT covered, never describe the cost as $0 or as free, even
  though the copay field reads 0. Not covered means the member owes the full
  billed amount.

WHEN THE TOOL IS UNSURE
- status "ambiguous": the question named more than one real service that this plan
  covers DIFFERENTLY. Ask which one they mean and list the options. Never pick.
- status "not_found": say you have no coverage rule for that service and will not
  guess, then list what you can check.
- status "unknown_code": say that code is not in this plan's rule set.
- status "roi_required": deliver the Release of Information message as given. Do
  not reveal any plan-specific detail.

PROVIDERS
- If the tool returns providers, include them. If it says no in-network specialist
  is accepting new patients, say so plainly - do not paper over it - and give the
  PCP referral step it provides.

STYLE
- Plain language for someone with no insurance background. No jargon.
- Reply in the member's preferred language: {member_language?}.
- End with the rule you relied on, formatted exactly as: (Based on: RULE0070 / MAPD)
  using the `grounded_on` and `plan_type` values returned by the tool.
- Under 120 words unless asked for more detail.
"""


# ---------------------------------------------------------------------------
# tools -- ADK function tools: the only place session state meets the pure core
#
# `member_id` is read from session state rather than accepted as an argument, so
# the model cannot invent or substitute one. Everything factual is computed by
# the answer section; these functions only marshal.
# ---------------------------------------------------------------------------

_STATUS = {
    Resolution.RESOLVED: "ok",
    Resolution.AMBIGUOUS: "ambiguous",
    Resolution.NOT_FOUND: "not_found",
    Resolution.UNKNOWN_CODE: "unknown_code",
}


def _record(tool_context: ToolContext, answer: BenefitsAnswer) -> None:
    """Stash the deterministic answer so the card is assembled from data, not prose."""
    tool_context.state[StateKeys.LAST_LOOKUP] = answer.model_dump(mode="json")

    from .session_context import record_finding

    record_finding(tool_context.state, AGENT_KEY, answer.model_dump(mode="json"))


def lookup_coverage(service_query: str, tool_context: ToolContext) -> dict[str, Any]:
    """Look up how a medical service is covered for the member in this session.

    Call this before answering ANY coverage, prior-authorization, or cost
    question. It is the only source of coverage truth.

    Args:
        service_query: The service as the caller described it, in their own words
            (for example "colonoscopy", "knee surgery", "MRI", or a CPT code such
            as "45378"). Pass the caller's phrasing; do not translate it into a
            code yourself.

    Returns:
        dict with `status` (one of "ok", "ambiguous", "not_found",
        "unknown_code", "roi_required", "no_member"), a ready-to-deliver
        `answer_text`, and the grounded facts: covered, prior_auth_required,
        cost, next_step, providers, grounded_on, plan_type.
    """
    from .session_context import record_intent

    record_intent(tool_context.state, AGENT_KEY)
    member_id = tool_context.state.get(StateKeys.SUBJECT_MEMBER_ID)
    roi_status = tool_context.state.get(StateKeys.ROI_STATUS)

    if not member_id:
        return {
            "status": "no_member",
            "answer_text": (
                "I need to know which member this is about before I can check "
                "plan-specific coverage."
            ),
        }

    answer = answer_benefits_question(service_query, member_id=member_id, roi_status=roi_status)
    _record(tool_context, answer)

    if not roi_permits_detail(roi_status):
        emit(
            EVENT_TYPE,
            {
                "session_id": tool_context.state.get(StateKeys.SESSION_ID),
                "member_id": member_id,
                "match_type": "refused_roi",
                "roi_status": roi_status,
            },
        )
        return {"status": "roi_required", "answer_text": answer.answer_text}

    payload = answer.model_dump(mode="json", exclude_none=False)
    payload["status"] = _STATUS[answer.resolution]

    emit(
        EVENT_TYPE,
        {
            "session_id": tool_context.state.get(StateKeys.SESSION_ID),
            "member_id": member_id,
            "cpt_code": answer.cpt_code,
            "matched_rule_id": answer.grounded_on[0] if answer.grounded_on else None,
            "plan_type": answer.plan_type,
            "match_type": answer.resolution.value,
            "answered_in_language": answer.language,
            "covered": answer.covered,
            "prior_auth_required": answer.prior_auth_required,
            "grounded_on": answer.grounded_on,
            "synthetic": True,
        },
    )
    return payload


def find_provider_tool(service_or_cpt: str, tool_context: ToolContext) -> dict[str, Any]:
    """Find in-network providers who can perform a service for this member.

    Use when the service needs prior authorization, or when the caller asks where
    they can get it done.

    Args:
        service_or_cpt: The service in plain words or as a CPT code
            (for example "colonoscopy" or "45378").

    Returns:
        dict with `status`, `providers` (never empty), `basis` describing which
        fallback was used, `specialty_availability`, and a `note` to relay.
    """
    from .session_context import record_intent, roi_blocked_payload

    record_intent(tool_context.state, "provider_directory")
    member_id = tool_context.state.get(StateKeys.SUBJECT_MEMBER_ID)
    if not member_id:
        return {"status": "no_member", "providers": []}
    if not roi_permits_detail(tool_context.state.get(StateKeys.ROI_STATUS)):
        return roi_blocked_payload(tool_context.state)

    result = find_provider(service_or_cpt, member_id)

    # A specialty that is in-network but has nobody accepting new patients is a
    # network-adequacy finding -- Sentinel's beat. One line, real compliance value.
    if result.specialty_availability == "none_accepting_new_patients":
        emit(
            NETWORK_GAP_EVENT,
            {
                "session_id": tool_context.state.get(StateKeys.SESSION_ID),
                "member_id": member_id,
                "specialty": result.specialty_requested,
                "member_state": load_members()[member_id].state,
                "detail": (
                    f"No in-network {result.specialty_requested} providers are "
                    "accepting new patients."
                ),
            },
        )

    payload = result.model_dump(mode="json")
    payload["status"] = "ok"
    return payload


# The pure `find_provider` above owns the plain name, so the tool wrapper is
# defined under a suffixed one -- but ADK derives the model-facing tool name from
# __name__, and the prompt and transcripts refer to it as `find_provider`.
find_provider_tool.__name__ = "find_provider"


# ---------------------------------------------------------------------------
# agent -- ADK definition
#
# Deliberately thin. Coverage is decided in the answer section; this layer only
# narrates and translates.
# ---------------------------------------------------------------------------

MODEL = os.getenv("BENEFITS_MODEL", "gemini-flash-latest")

DESCRIPTION = (
    "Answers member questions about coverage, prior authorization, and cost "
    "sharing for medical services, grounded in the plan's coverage rules."
)


def build_agent(model: str | None = None) -> "LlmAgent":
    # Imported here rather than at module scope so the deterministic core above
    # stays importable without google-adk installed.
    from google.adk.agents import LlmAgent

    return LlmAgent(
        model=model or MODEL,
        name="benefits_qa",
        description=DESCRIPTION,
        instruction=SYSTEM_PROMPT,
        tools=[lookup_coverage, find_provider_tool],
    )


def __getattr__(name: str):
    #: Import this from the orchestrator and wrap it:
    #:     from google.adk.tools.agent_tool import AgentTool
    #:     AgentTool(agent=benefits_agent)
    #: Agent-as-tool keeps the orchestrator in control, unlike description-transfer
    #: sub_agents, which hand off the turn entirely.
    #:
    #: Built on first access, not at import: constructing it needs google-adk,
    #: and importing this module must not. No network I/O either way.
    if name == "benefits_agent":
        agent = build_agent()
        globals()["benefits_agent"] = agent
        return agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AGENT_KEY",
    "ALIASES",
    "AMBIGUITY_GROUPS",
    "BenefitsAnswer",
    "BenefitsKB",
    "BigQueryCoverageRulesClient",
    "BigQueryMemberRecordsClient",
    "BigQueryProviderDirectoryClient",
    "BigQueryUnavailable",
    "CPT_SPECIALTY",
    "CostBreakdown",
    "CoverageLookupResult",
    "CoverageRule",
    "CoverageRulesClient",
    "CsvBenefitsKB",
    "CsvCoverageRulesClient",
    "CsvMemberRecordsClient",
    "CsvProviderDirectoryClient",
    "DATASETS",
    "DESCRIPTION",
    "EVENT_LOG",
    "EVENT_TYPE",
    "FALLBACK_SOURCE",
    "MODEL",
    "Member",
    "MemberRecordsClient",
    "NETWORK_GAP_EVENT",
    "PLAN_TYPES",
    "Provider",
    "ProviderDirectoryClient",
    "ProviderMatch",
    "ProviderResult",
    "ROI_ALLOWED",
    "Resolution",
    "SYSTEM_PROMPT",
    "Settings",
    "StateKeys",
    "all_codes",
    "answer_benefits_question",
    "benefits_agent",
    "build_agent",
    "coerce_bool",
    "coerce_int",
    "coerce_str",
    "cost_breakdown",
    "data_source",
    "descriptions",
    "display_name",
    "drain",
    "emit",
    "find_provider",
    "find_provider_tool",
    "get_coverage_rules_client",
    "get_member_records_client",
    "get_provider_directory_client",
    "get_settings",
    "load_members",
    "load_providers",
    "load_rules",
    "lookup_coverage",
    "normalize",
    "parse_bool",
    "reset_cache",
    "reset_settings_cache",
    "roi_permits_detail",
    "rule_index",
    "rules_agree",
    "to_coverage_rule",
    "to_member",
    "to_provider",
]
