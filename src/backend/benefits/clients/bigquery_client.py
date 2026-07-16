"""BigQuery-backed clients.

Each client pulls its whole table into a DataFrame once, at construction. That is
appropriate here and not a shortcut: the three tables are 80, 200 and 50 rows, so
the entire dataset is a few hundred rows. Loading eagerly buys per-query latency
of zero, no round-trip inside the request path, and no partial-failure states
mid-conversation.

pandas and google-cloud-bigquery are an optional extra (`.[bigquery]`) and are
imported lazily, so a machine without them -- or with a broken install -- falls
back to CSV instead of failing to import.
"""

import logging
from typing import TYPE_CHECKING, Any

from ..models import CoverageRule, Member, Provider
from ..settings import Settings, get_settings
from .mapping import to_coverage_rule, to_member, to_provider

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


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
