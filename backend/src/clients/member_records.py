"""Member & ROI-authorization data access.

`MemberRecordsClient` is the interface every consumer codes against. The real
implementation queries **BigQuery** (dataset `humana_hackathon`); the CSVs in
`datasets/` are only the schema reference for those tables. `FakeMemberRecordsClient`
is an in-memory stand-in used by unit tests so the deterministic logic can be verified
with no BigQuery access or credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
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
        if client is not None:
            self._client = client
        else:
            from google.cloud import bigquery

            self._client = bigquery.Client(
                project=self.settings.google_cloud_project,
                location=self.settings.bigquery_location,
            )

    def _query_one(self, sql: str, params: dict):
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in params.items()
            ]
        )
        return list(self._client.query(sql, job_config=job_config).result())

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


class FakeMemberRecordsClient:
    """In-memory implementation for unit tests. No BigQuery, no credentials."""

    def __init__(self, authorizations: list[Authorization]):
        self._auths: dict[str, list[Authorization]] = {}
        for a in authorizations:
            self._auths.setdefault(a.member_id, []).append(a)

    def get_authorizations(self, member_id: str) -> list[Authorization]:
        return list(self._auths.get(member_id, []))
