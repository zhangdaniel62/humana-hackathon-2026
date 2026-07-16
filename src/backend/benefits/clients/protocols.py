"""Data-source protocols.

One protocol per table the Benefits agent reads. Implementations must return the
same model objects regardless of backend, so everything above this layer --
kb.py, providers.py, answer.py -- is backend-agnostic and never sees a DataFrame.

claims.csv is deliberately absent: it belongs to the Claim Story agent, and it
disagrees with coverage_rules on prior-auth for 50 of 880 rows, so this module
must never read it.
"""

from typing import Protocol, runtime_checkable

from ..models import CoverageRule, Member, Provider


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
