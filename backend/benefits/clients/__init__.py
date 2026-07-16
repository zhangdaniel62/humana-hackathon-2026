"""Client factory: the settings toggle and the BigQuery -> CSV fallback.

Fallback is per-table and happens at construction, so a session can never start
against BigQuery and then silently change source mid-conversation.

The fallback is safe precisely because the CSVs hold the same data, so an answer
is equally grounded either way -- but it is never silent: it logs a warning and
the source actually used is reported on every answer as `BenefitsAnswer.data_source`.
"""

import logging

from ..settings import Settings, get_settings
from .csv_client import (
    CsvCoverageRulesClient,
    CsvMemberRecordsClient,
    CsvProviderDirectoryClient,
)
from .protocols import CoverageRulesClient, MemberRecordsClient, ProviderDirectoryClient

log = logging.getLogger(__name__)

FALLBACK_SOURCE = "csv_fallback"

_CSV = {
    "coverage_rules": CsvCoverageRulesClient,
    "members": CsvMemberRecordsClient,
    "providers": CsvProviderDirectoryClient,
}


def _bigquery_impls() -> dict[str, type]:
    from .bigquery_client import (
        BigQueryCoverageRulesClient,
        BigQueryMemberRecordsClient,
        BigQueryProviderDirectoryClient,
    )

    return {
        "coverage_rules": BigQueryCoverageRulesClient,
        "members": BigQueryMemberRecordsClient,
        "providers": BigQueryProviderDirectoryClient,
    }


def _build(kind: str, settings: Settings):
    if settings.data_source != "bigquery":
        return _CSV[kind](settings=settings)

    try:
        return _bigquery_impls()[kind](settings=settings)
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


__all__ = [
    "CoverageRulesClient",
    "CsvCoverageRulesClient",
    "CsvMemberRecordsClient",
    "CsvProviderDirectoryClient",
    "FALLBACK_SOURCE",
    "MemberRecordsClient",
    "ProviderDirectoryClient",
    "get_coverage_rules_client",
    "get_member_records_client",
    "get_provider_directory_client",
]
