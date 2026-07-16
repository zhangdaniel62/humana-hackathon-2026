"""Tests for the data-client layer: protocols, the toggle, and the fallback.

The load-bearing test here is `test_bigquery_and_csv_produce_identical_models`.
The two backends hand over different Python types for the same column -- BigQuery
gives a real bool where the CSV gives the string "false" -- so "same data, either
source" is a claim that has to be proved, not assumed. Everything else in the
module trusts it.
"""

import csv as stdlib_csv
from pathlib import Path

import pytest

from backend.src.agents import benefits as agent_mod
from backend.src.agents.benefits import (
    FALLBACK_SOURCE,
    BigQueryCoverageRulesClient,
    BigQueryMemberRecordsClient,
    BigQueryProviderDirectoryClient,
    BigQueryUnavailable,
    CoverageRulesClient,
    CsvCoverageRulesClient,
    CsvMemberRecordsClient,
    CsvProviderDirectoryClient,
    MemberRecordsClient,
    ProviderDirectoryClient,
    Settings,
    coerce_bool,
    coerce_int,
    coerce_str,
    get_coverage_rules_client,
    get_member_records_client,
    get_provider_directory_client,
)

pd = pytest.importorskip("pandas")

# tests -> backend -> repo root
DATASETS = Path(__file__).resolve().parents[2] / "datasets"

# Columns BigQuery would hand back as native types rather than strings.
_BOOL_COLS = {"covered", "prior_auth_required", "accepting_new_patients"}
_INT_COLS = {"cost_share_pct", "copay"}


def _bq_style_frame(filename: str) -> pd.DataFrame:
    """Build a DataFrame with the dtypes BigQuery would actually return.

    Reading the CSV with pandas would leave "true"/"false" as strings and prove
    nothing; the point is to exercise real bools, int64 and NULL.
    """
    with (DATASETS / filename).open(newline="", encoding="utf-8") as fh:
        rows = list(stdlib_csv.DictReader(fh))

    for row in rows:
        for col in _BOOL_COLS & row.keys():
            row[col] = row[col] == "true"
        for col in _INT_COLS & row.keys():
            row[col] = int(row[col])
        if row.get("notes") == "":
            row["notes"] = None  # BigQuery NULL

    df = pd.DataFrame(rows)
    for col in _BOOL_COLS & set(df.columns):
        df[col] = df[col].astype("bool")
    for col in _INT_COLS & set(df.columns):
        df[col] = df[col].astype("int64")
    return df


class _FakeJob:
    def __init__(self, df):
        self._df = df

    def to_dataframe(self):
        return self._df


class FakeBigQuery:
    """Stands in for google.cloud.bigquery.Client."""

    def __init__(self, frames: dict[str, pd.DataFrame], fail: bool = False):
        self.frames = frames
        self.fail = fail
        self.queries: list[str] = []

    def query(self, sql: str):
        self.queries.append(sql)
        if self.fail:
            raise RuntimeError("bigquery is down")
        for name, df in self.frames.items():
            if name in sql:
                return _FakeJob(df)
        raise RuntimeError(f"no such table in {sql}")


@pytest.fixture
def bq_settings() -> Settings:
    return Settings(
        data_source="bigquery",
        bq_project="proj",
        bq_dataset="ds",
        datasets_dir=DATASETS,
    )


@pytest.fixture
def csv_settings() -> Settings:
    return Settings(data_source="csv", datasets_dir=DATASETS)


@pytest.fixture
def fake_bq() -> FakeBigQuery:
    return FakeBigQuery(
        {
            "coverage_rules": _bq_style_frame("coverage_rules.csv"),
            "members": _bq_style_frame("members.csv"),
            "providers": _bq_style_frame("providers.csv"),
        }
    )


@pytest.fixture(autouse=True)
def _clear_loader_cache():
    agent_mod.reset_cache()
    yield
    agent_mod.reset_cache()


# --------------------------------------------------------------------------
# The crux
# --------------------------------------------------------------------------

def test_bigquery_and_csv_produce_identical_models(bq_settings, csv_settings, fake_bq):
    """Same rows, same models -- despite BigQuery's bools/int64/NULLs."""
    pairs = [
        (BigQueryCoverageRulesClient, CsvCoverageRulesClient),
        (BigQueryMemberRecordsClient, CsvMemberRecordsClient),
        (BigQueryProviderDirectoryClient, CsvProviderDirectoryClient),
    ]
    for bq_cls, csv_cls in pairs:
        from_bq = bq_cls(settings=bq_settings, bq_client=fake_bq).fetch_all()
        from_csv = csv_cls(settings=csv_settings).fetch_all()
        assert from_bq == from_csv, f"{bq_cls.__name__} diverges from {csv_cls.__name__}"


def test_bigquery_bools_survive_the_round_trip(bq_settings, fake_bq):
    """A real BigQuery BOOL must not be re-parsed as the string 'True'."""
    rules = BigQueryCoverageRulesClient(settings=bq_settings, bq_client=fake_bq).fetch_all()
    not_covered = [r for r in rules if not r.covered]
    assert len(not_covered) == 8
    assert sum(r.prior_auth_required for r in rules) == 19


def test_bigquery_null_notes_become_empty_strings(bq_settings, fake_bq):
    rules = BigQueryCoverageRulesClient(settings=bq_settings, bq_client=fake_bq).fetch_all()
    for r in rules:
        assert (r.notes == "Requires in-network provider") == r.prior_auth_required
        assert r.notes in ("", "Requires in-network provider")


def test_loads_whole_table_once_at_init(bq_settings, fake_bq):
    client = BigQueryCoverageRulesClient(settings=bq_settings, bq_client=fake_bq)
    assert len(fake_bq.queries) == 1
    assert len(client.df) == 80
    client.fetch_all()
    client.fetch_all()
    assert len(fake_bq.queries) == 1  # no per-query round trips


def test_query_targets_the_configured_table(bq_settings, fake_bq):
    BigQueryCoverageRulesClient(settings=bq_settings, bq_client=fake_bq)
    assert "`proj.ds.coverage_rules`" in fake_bq.queries[0]


# --------------------------------------------------------------------------
# Toggle and fallback
# --------------------------------------------------------------------------

def test_csv_is_the_default():
    assert Settings(datasets_dir=DATASETS).data_source == "csv"


def test_toggle_selects_csv(csv_settings):
    client = get_coverage_rules_client(csv_settings)
    assert isinstance(client, CsvCoverageRulesClient)
    assert client.source == "csv"


def test_falls_back_to_csv_when_bigquery_fails(bq_settings, monkeypatch):
    """The demo must not hard-fail on a BigQuery outage."""

    def explode(self):
        raise BigQueryUnavailable("no credentials")

    monkeypatch.setattr(agent_mod._BigQueryClient, "_load_dataframe", explode)

    client = get_coverage_rules_client(bq_settings)
    assert isinstance(client, CsvCoverageRulesClient)
    assert client.source == FALLBACK_SOURCE
    assert len(client.fetch_all()) == 80  # still fully grounded


def test_fallback_is_reported_not_silent(bq_settings, monkeypatch, caplog):

    monkeypatch.setattr(
        agent_mod._BigQueryClient,
        "_load_dataframe",
        lambda self: (_ for _ in ()).throw(BigQueryUnavailable("boom")),
    )
    with caplog.at_level("WARNING"):
        get_coverage_rules_client(bq_settings)
    assert "falling back to CSV" in caplog.text


def test_strict_mode_refuses_to_fall_back(monkeypatch):

    monkeypatch.setattr(
        agent_mod._BigQueryClient,
        "_load_dataframe",
        lambda self: (_ for _ in ()).throw(BigQueryUnavailable("boom")),
    )
    strict = Settings(
        data_source="bigquery",
        bq_project="p",
        bq_dataset="d",
        bigquery_fallback_to_csv=False,
        datasets_dir=DATASETS,
    )
    with pytest.raises(BigQueryUnavailable):
        get_coverage_rules_client(strict)


def test_empty_table_is_treated_as_misconfiguration(bq_settings):
    empty = FakeBigQuery({"coverage_rules": pd.DataFrame()})
    with pytest.raises(BigQueryUnavailable, match="zero rows"):
        BigQueryCoverageRulesClient(settings=bq_settings, bq_client=empty)


def test_missing_extra_degrades_rather_than_crashing(bq_settings, monkeypatch):
    """No pandas/bigquery installed must mean CSV, not ImportError at import."""
    def no_extra(settings=None):
        raise ImportError("No module named 'google.cloud.bigquery'")

    monkeypatch.setitem(agent_mod._BIGQUERY, "coverage_rules", no_extra)
    client = get_coverage_rules_client(bq_settings)
    assert isinstance(client, CsvCoverageRulesClient)
    assert client.source == FALLBACK_SOURCE


def test_bigquery_config_is_required_when_selected():
    with pytest.raises(ValueError, match="BENEFITS_BQ_PROJECT"):
        Settings(data_source="bigquery", datasets_dir=DATASETS)


def test_table_ref_is_fully_qualified(bq_settings):
    assert bq_settings.table_ref("members") == "proj.ds.members"


def test_table_names_are_overridable(fake_bq):
    s = Settings(
        data_source="bigquery",
        bq_project="p",
        bq_dataset="d",
        bq_coverage_rules_table="coverage_rules_v2",
        datasets_dir=DATASETS,
    )
    assert s.table_ref(s.bq_coverage_rules_table) == "p.d.coverage_rules_v2"


# --------------------------------------------------------------------------
# Protocol conformance
# --------------------------------------------------------------------------

def test_all_impls_satisfy_their_protocol(csv_settings, bq_settings, fake_bq):
    assert isinstance(CsvCoverageRulesClient(settings=csv_settings), CoverageRulesClient)
    assert isinstance(CsvMemberRecordsClient(settings=csv_settings), MemberRecordsClient)
    assert isinstance(CsvProviderDirectoryClient(settings=csv_settings), ProviderDirectoryClient)
    assert isinstance(
        BigQueryCoverageRulesClient(settings=bq_settings, bq_client=fake_bq),
        CoverageRulesClient,
    )
    assert isinstance(
        BigQueryMemberRecordsClient(settings=bq_settings, bq_client=fake_bq),
        MemberRecordsClient,
    )
    assert isinstance(
        BigQueryProviderDirectoryClient(settings=bq_settings, bq_client=fake_bq),
        ProviderDirectoryClient,
    )


def test_factories_return_clients_for_every_table(csv_settings):
    assert len(get_coverage_rules_client(csv_settings).fetch_all()) == 80
    assert len(get_member_records_client(csv_settings).fetch_all()) == 200
    assert len(get_provider_directory_client(csv_settings).fetch_all()) == 50


# --------------------------------------------------------------------------
# Coercion
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("false", False), ("TRUE", True), ("", False),
     (True, True), (False, False), (1, True), (0, False), (None, False)],
)
def test_coerce_bool(value, expected):
    assert coerce_bool(value) is expected


def test_coerce_bool_handles_numpy(bq_settings):
    import numpy as np

    assert coerce_bool(np.bool_(True)) is True
    assert coerce_bool(np.bool_(False)) is False


@pytest.mark.parametrize("value", ["maybe", "2", 7, object()])
def test_coerce_bool_rejects_garbage(value):
    with pytest.raises(ValueError):
        coerce_bool(value)


def test_coerce_int_handles_numpy_and_blanks():
    import numpy as np

    assert coerce_int(np.int64(20)) == 20
    assert coerce_int("") == 0
    assert coerce_int(None) == 0
    with pytest.raises(ValueError):
        coerce_int(1.5)


def test_coerce_str_handles_null_and_nan():
    assert coerce_str(None) == ""
    assert coerce_str(float("nan")) == ""
    assert coerce_str("x") == "x"


# --------------------------------------------------------------------------
# The facade keeps its guarantees regardless of backend
# --------------------------------------------------------------------------

def test_grid_assert_runs_against_bigquery_rows(bq_settings, monkeypatch, fake_bq):
    """A stale or mis-pointed BQ table must fail at load, not mid-demo."""
    truncated = fake_bq.frames["coverage_rules"].head(40)
    partial = FakeBigQuery({"coverage_rules": truncated})

    monkeypatch.setitem(
        agent_mod._BIGQUERY,
        "coverage_rules",
        lambda settings: BigQueryCoverageRulesClient(settings=settings, bq_client=partial),
    )
    monkeypatch.setattr(agent_mod, "get_coverage_rules_client",
                        lambda: agent_mod._build("coverage_rules", bq_settings))
    with pytest.raises(AssertionError, match="expected 80"):
        agent_mod.load_rules()


def test_answer_reports_its_data_source():
    from backend.src.agents.benefits import answer_benefits_question

    a = answer_benefits_question("colonoscopy", member_id="MBR00183")
    assert a.data_source == "csv"
    assert a.grounded_on == ["RULE0070"]


def test_each_table_is_fetched_from_exactly_one_client(monkeypatch, csv_settings):
    """Constructing a client runs a BigQuery query, so building one twice per
    table would double the round trips. data_source() must reuse, not rebuild."""
    built: list[str] = []

    real_build = agent_mod._build

    def counting_build(kind, settings):
        built.append(kind)
        return real_build(kind, settings)

    monkeypatch.setattr(agent_mod, "_build", counting_build)
    for name in ("get_coverage_rules_client", "get_member_records_client",
                 "get_provider_directory_client"):
        monkeypatch.setattr(
            agent_mod, name,
            lambda kind=name: counting_build(
                {"get_coverage_rules_client": "coverage_rules",
                 "get_member_records_client": "members",
                 "get_provider_directory_client": "providers"}[kind],
                csv_settings,
            ),
        )

    agent_mod.load_rules()
    agent_mod.load_members()
    agent_mod.load_providers()
    agent_mod.data_source()
    agent_mod.rule_index()
    agent_mod.descriptions()

    assert sorted(built) == ["coverage_rules", "members", "providers"]
