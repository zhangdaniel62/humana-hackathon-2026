"""Offline and fallback tests for ROI authorization data access."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.clients.member_records import (
    CsvMemberRecordsClient,
    FallbackMemberRecordsClient,
    create_member_records_client,
)
from tests.test_claims_repository import build_test_settings


def test_csv_client_returns_synthetic_authorizations() -> None:
    auths = CsvMemberRecordsClient().get_authorizations("MBR00183")

    assert {auth.authorized_caller_name for auth in auths} == {
        "Aaron Guerrero",
        "Dustin Ramirez",
        "Jessica King",
    }


def test_fallback_client_uses_csv_when_primary_fails() -> None:
    primary = MagicMock()
    primary.get_authorizations.side_effect = RuntimeError("offline")

    auths = FallbackMemberRecordsClient(
        primary,
        CsvMemberRecordsClient(),
    ).get_authorizations("MBR00183")

    assert len(auths) == 3


def test_factory_falls_back_when_lazy_bigquery_client_cannot_initialize() -> None:
    with patch(
        "google.cloud.bigquery.Client",
        side_effect=RuntimeError("no credentials"),
    ):
        client = create_member_records_client(build_test_settings())
        auths = client.get_authorizations("MBR00183")

    assert len(auths) == 3
