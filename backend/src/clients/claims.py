"""BigQuery-backed claim access."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Protocol

from google.cloud import bigquery
from pydantic import ValidationError

from ..models.claims import ClaimRow
from ..settings import Settings

CLAIM_COLUMNS = (
    "claim_id",
    "member_id",
    "provider_id",
    "provider_name",
    "service_date",
    "submitted_date",
    "adjudication_date",
    "cpt_code",
    "cpt_description",
    "diagnosis_code",
    "claim_status",
    "denial_code",
    "denial_reason",
    "denial_fixable",
    "billed_amount",
    "paid_amount",
    "referral_on_file",
    "prior_auth_required",
    "prior_auth_obtained",
    "denial_risk_flag",
    "modifier_mismatch",
    "reprocessing_days_est",
)

_PROJECT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_DATASET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ClaimsRepositoryError(RuntimeError):
    """A claim lookup failed before a trustworthy result was available."""


class ClaimDataIntegrityError(ClaimsRepositoryError):
    """BigQuery returned claim data that violates repository expectations."""


class ClaimsRepository(Protocol):
    """Interface used by claim-story preparation and tests."""

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        """Return the exact claim or ``None`` when it does not exist."""

    def list_actionable_claims(self, *, limit: int = 500) -> list[ClaimRow]:
        """Return a bounded, stable list of Pending/In Review claims."""


class CsvClaimsRepository:
    """Exact-claim repository backed by the synthetic CSV fallback."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (
            Path(__file__).resolve().parents[3] / "datasets" / "claims.csv"
        )
        self._claims: dict[str, ClaimRow] | None = None

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        if self._claims is None:
            self._claims = self._load()
        return self._claims.get(claim_id)

    def list_actionable_claims(self, *, limit: int = 500) -> list[ClaimRow]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if self._claims is None:
            self._claims = self._load()
        return [
            claim
            for claim in sorted(self._claims.values(), key=lambda item: item.claim_id)
            if claim.claim_status.value in {"Pending", "In Review"}
        ][:limit]

    def _load(self) -> dict[str, ClaimRow]:
        claims: dict[str, ClaimRow] = {}
        with self.path.open(newline="", encoding="utf-8") as claim_file:
            for row in csv.DictReader(claim_file):
                normalized = {
                    key: value if value != "" else None
                    for key, value in row.items()
                }
                claim = ClaimRow.model_validate(normalized)
                if claim.claim_id in claims:
                    raise ClaimDataIntegrityError(
                        f"Duplicate claim ID {claim.claim_id} in {self.path}"
                    )
                claims[claim.claim_id] = claim
        return claims


class FallbackClaimsRepository:
    """Use BigQuery first and the synthetic CSV only when it is unavailable."""

    def __init__(
        self,
        primary: ClaimsRepository,
        fallback: ClaimsRepository,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        try:
            return self.primary.get_claim(claim_id)
        except ClaimsRepositoryError:
            return self.fallback.get_claim(claim_id)

    def list_actionable_claims(self, *, limit: int = 500) -> list[ClaimRow]:
        try:
            return self.primary.list_actionable_claims(limit=limit)
        except ClaimsRepositoryError:
            return self.fallback.list_actionable_claims(limit=limit)


class BigQueryClaimsRepository:
    """Read exact claims from the configured BigQuery dataset."""

    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._validate_table_components()
        self.client = client or bigquery.Client(
            project=settings.google_cloud_project,
            location=settings.bigquery_location,
        )

    @property
    def table_id(self) -> str:
        """Return the fully qualified claims table identifier."""

        return (
            f"{self.settings.google_cloud_project}."
            f"{self.settings.bigquery_dataset}.claims"
        )

    def get_claim(self, claim_id: str) -> ClaimRow | None:
        """Fetch one claim using a parameterized query."""

        sql = f"""
            SELECT
              {", ".join(CLAIM_COLUMNS)}
            FROM `{self.table_id}`
            WHERE claim_id = @claim_id
            LIMIT 2
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id)
            ]
        )

        try:
            query_job = self.client.query(
                sql,
                job_config=job_config,
                location=self.settings.bigquery_location,
            )
            rows = list(query_job.result(max_results=2))
        except Exception as exc:
            raise ClaimsRepositoryError(
                f"BigQuery lookup failed for claim {claim_id}"
            ) from exc

        if not rows:
            return None
        if len(rows) > 1:
            raise ClaimDataIntegrityError(
                f"Expected one row for claim {claim_id}, found {len(rows)}"
            )

        try:
            return ClaimRow.model_validate(dict(rows[0]))
        except (TypeError, ValidationError, ValueError) as exc:
            raise ClaimDataIntegrityError(
                f"Claim {claim_id} does not match the expected schema"
            ) from exc

    def list_actionable_claims(self, *, limit: int = 500) -> list[ClaimRow]:
        """Fetch a bounded population using the same eligibility as readiness."""

        if limit < 1:
            raise ValueError("limit must be positive")
        sql = f"""
            SELECT
              {", ".join(CLAIM_COLUMNS)}
            FROM `{self.table_id}`
            WHERE claim_status IN ('Pending', 'In Review')
            ORDER BY claim_id
            LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", min(limit, 5_000))
            ]
        )
        try:
            rows = list(
                self.client.query(
                    sql,
                    job_config=job_config,
                    location=self.settings.bigquery_location,
                ).result(max_results=min(limit, 5_000))
            )
            return [ClaimRow.model_validate(dict(row)) for row in rows]
        except (TypeError, ValidationError, ValueError) as exc:
            raise ClaimDataIntegrityError(
                "The actionable-claim population does not match the expected schema"
            ) from exc
        except Exception as exc:
            raise ClaimsRepositoryError(
                "BigQuery actionable-claim scan failed"
            ) from exc

    def _validate_table_components(self) -> None:
        """Reject malformed identifiers before interpolating a table name."""

        if not _PROJECT_PATTERN.fullmatch(self.settings.google_cloud_project):
            raise ValueError("google_cloud_project is not a valid table identifier")
        if not _DATASET_PATTERN.fullmatch(self.settings.bigquery_dataset):
            raise ValueError("bigquery_dataset is not a valid table identifier")


def create_claims_repository(settings: Settings) -> ClaimsRepository:
    """Build the live repository with a deterministic offline fallback."""

    fallback = CsvClaimsRepository()
    try:
        primary = BigQueryClaimsRepository(settings)
    except Exception:
        return fallback
    return FallbackClaimsRepository(primary, fallback)
