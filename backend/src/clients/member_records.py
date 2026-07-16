"""Member & ROI-authorization data access.

`MemberRecordsClient` is the interface every consumer codes against. The real
implementation queries **BigQuery** (dataset `humana_hackathon`); the CSVs in
`datasets/` are only the schema reference for those tables. `FakeMemberRecordsClient`
is an in-memory stand-in used by unit tests so the deterministic logic can be verified
with no BigQuery access or credentials.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Authorization:
    auth_id: str
    member_id: str
    authorized_caller_name: str
    relationship: str
    auth_on_file: bool
    expiration_date: str  # ISO string or "" if none
    auth_expired: bool


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


class MemberRecordsClient(Protocol):
    """Interface the ROI Gatekeeper depends on.

    NOTE: the ROI/claims population uses `MBR#####` member ids (roi_authorizations,
    claims), which do NOT match the `members` table (`MEM-#####`). So the ROI gate does
    not join to `members`; the "caller is the member" check is identity-based
    (caller_id == subject_member_id), per plan note #5a.
    """

    def get_authorizations(self, member_id: str) -> list[Authorization]: ...


class BigQueryMemberRecordsClient:
    """Reads members and ROI authorizations from BigQuery.

    Auth + project come from the app `Settings` (Vertex/ADC). Imported lazily so
    this module can be imported without a populated `.env`.
    """

    def __init__(self, settings=None, client=None):
        from src.settings import settings as default_settings

        self.settings = settings or default_settings
        self._client = client

    def _get_client(self):
        """Create the BigQuery client only when an ROI lookup actually runs."""

        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(
                project=self.settings.google_cloud_project,
                location=self.settings.bigquery_location,
            )
        return self._client

    def _query_one(self, sql: str, params: dict):
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in params.items()
            ]
        )
        return list(self._get_client().query(sql, job_config=job_config).result())

    def get_authorizations(self, member_id: str) -> list[Authorization]:
        table = self.settings.table(self.settings.roi_authorizations_table)
        sql = (
            "SELECT auth_id, member_id, authorized_caller_name, relationship, "
            "auth_on_file, expiration_date, auth_expired "
            f"FROM `{table}` WHERE member_id = @member_id"
        )
        rows = self._query_one(sql, {"member_id": member_id})
        return [
            Authorization(
                auth_id=r["auth_id"],
                member_id=r["member_id"],
                authorized_caller_name=(r["authorized_caller_name"] or "").strip(),
                relationship=(r["relationship"] or "").strip(),
                auth_on_file=_to_bool(r["auth_on_file"]),
                expiration_date=str(r["expiration_date"] or "").strip(),
                auth_expired=_to_bool(r["auth_expired"]),
            )
            for r in rows
        ]


class CsvMemberRecordsClient:
    """Reads the synthetic ROI authorization snapshot for offline demos."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (
            Path(__file__).resolve().parents[3]
            / "datasets"
            / "roi_authorizations.csv"
        )
        self._auths: dict[str, list[Authorization]] | None = None

    def get_authorizations(self, member_id: str) -> list[Authorization]:
        if self._auths is None:
            self._auths = self._load()
        return list(self._auths.get(member_id, []))

    def _load(self) -> dict[str, list[Authorization]]:
        auths: dict[str, list[Authorization]] = {}
        with self.path.open(newline="", encoding="utf-8") as auth_file:
            for row in csv.DictReader(auth_file):
                authorization = Authorization(
                    auth_id=row["auth_id"].strip(),
                    member_id=row["member_id"].strip(),
                    authorized_caller_name=row[
                        "authorized_caller_name"
                    ].strip(),
                    relationship=row["relationship"].strip(),
                    auth_on_file=_to_bool(row["auth_on_file"]),
                    expiration_date=row["expiration_date"].strip(),
                    auth_expired=_to_bool(row["auth_expired"]),
                )
                auths.setdefault(authorization.member_id, []).append(
                    authorization
                )
        return auths


class FallbackMemberRecordsClient:
    """Use BigQuery first and the synthetic CSV if the live lookup fails."""

    def __init__(
        self,
        primary: MemberRecordsClient,
        fallback: MemberRecordsClient,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_authorizations(self, member_id: str) -> list[Authorization]:
        try:
            return self.primary.get_authorizations(member_id)
        except Exception:
            return self.fallback.get_authorizations(member_id)


def create_member_records_client(settings=None) -> MemberRecordsClient:
    """Build the live ROI client with a deterministic offline fallback."""

    fallback = CsvMemberRecordsClient()
    try:
        primary = BigQueryMemberRecordsClient(settings=settings)
    except Exception:
        return fallback
    return FallbackMemberRecordsClient(primary, fallback)


class FakeMemberRecordsClient:
    """In-memory implementation for unit tests. No BigQuery, no credentials."""

    def __init__(self, authorizations: list[Authorization]):
        self._auths: dict[str, list[Authorization]] = {}
        for a in authorizations:
            self._auths.setdefault(a.member_id, []).append(a)

    def get_authorizations(self, member_id: str) -> list[Authorization]:
        return list(self._auths.get(member_id, []))
