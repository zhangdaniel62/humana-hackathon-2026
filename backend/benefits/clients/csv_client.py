"""CSV-backed clients. stdlib only -- no pandas, no network, no credentials.

This is the fallback path, so it deliberately depends on nothing that can fail
to install or time out. It is also the default.
"""

import csv
from pathlib import Path
from typing import Any

from ..models import CoverageRule, Member, Provider
from ..settings import Settings, get_settings
from .mapping import to_coverage_rule, to_member, to_provider


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
