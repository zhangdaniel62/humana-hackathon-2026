"""Tests for the BigQuery claims repository."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.clients.claims import (
    BigQueryClaimsRepository,
    ClaimDataIntegrityError,
    ClaimsRepositoryError,
    CsvClaimsRepository,
    FallbackClaimsRepository,
    create_claims_repository,
)
from src.settings import Settings
from tests.claim_fixtures import claim_for_status
from src.models.claims import ClaimStatus


def build_test_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "google_cloud_project": "test-project",
        "google_cloud_location": "us-central1",
        "google_genai_use_vertexai": True,
        "model_name": "gemini-test",
        "bigquery_dataset": "test_dataset",
        "bigquery_location": "US",
        "gcs_bucket": "test-bucket",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeQueryJob:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.max_results: int | None = None

    def result(self, max_results: int | None = None) -> list[dict]:
        self.max_results = max_results
        return self.rows


class BigQueryClaimsRepositoryTests(unittest.TestCase):
    def test_constructs_client_from_settings(self) -> None:
        settings = build_test_settings()
        with patch("src.clients.claims.bigquery.Client") as client_class:
            BigQueryClaimsRepository(settings)

        client_class.assert_called_once_with(
            project="test-project",
            location="US",
        )

    def test_parameterized_query_and_row_validation(self) -> None:
        claim = claim_for_status(ClaimStatus.DENIED)
        query_job = FakeQueryJob([claim.model_dump(mode="python")])
        client = MagicMock()
        client.query.return_value = query_job
        repository = BigQueryClaimsRepository(build_test_settings(), client=client)

        result = repository.get_claim(claim.claim_id)

        self.assertEqual(claim, result)
        query, kwargs = client.query.call_args
        self.assertIn("FROM `test-project.test_dataset.claims`", query[0])
        self.assertIn("WHERE claim_id = @claim_id", query[0])
        self.assertNotIn(claim.claim_id, query[0])
        self.assertEqual("US", kwargs["location"])
        parameter = kwargs["job_config"].query_parameters[0]
        self.assertEqual("claim_id", parameter.name)
        self.assertEqual(claim.claim_id, parameter.value)
        self.assertEqual(2, query_job.max_results)

    def test_not_found_returns_none(self) -> None:
        client = MagicMock()
        client.query.return_value = FakeQueryJob([])
        repository = BigQueryClaimsRepository(build_test_settings(), client=client)

        self.assertIsNone(repository.get_claim("CLM999999"))

    def test_duplicate_rows_raise_data_integrity_error(self) -> None:
        claim = claim_for_status(ClaimStatus.PAID).model_dump(mode="python")
        client = MagicMock()
        client.query.return_value = FakeQueryJob([claim, claim])
        repository = BigQueryClaimsRepository(build_test_settings(), client=client)

        with self.assertRaises(ClaimDataIntegrityError):
            repository.get_claim(claim["claim_id"])

    def test_invalid_row_raises_data_integrity_error(self) -> None:
        claim = claim_for_status(ClaimStatus.PAID).model_dump(mode="python")
        claim.pop("provider_id")
        client = MagicMock()
        client.query.return_value = FakeQueryJob([claim])
        repository = BigQueryClaimsRepository(build_test_settings(), client=client)

        with self.assertRaises(ClaimDataIntegrityError):
            repository.get_claim(claim["claim_id"])

    def test_api_errors_are_wrapped(self) -> None:
        client = MagicMock()
        client.query.side_effect = RuntimeError("network unavailable")
        repository = BigQueryClaimsRepository(build_test_settings(), client=client)

        with self.assertRaises(ClaimsRepositoryError):
            repository.get_claim("CLM000001")

    def test_invalid_dataset_identifier_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BigQueryClaimsRepository(
                build_test_settings(bigquery_dataset="bad-dataset"),
                client=MagicMock(),
            )


class OfflineClaimsRepositoryTests(unittest.TestCase):
    def test_csv_repository_returns_exact_synthetic_claim(self) -> None:
        claim = CsvClaimsRepository().get_claim("CLM000377")

        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual("MBR00087", claim.member_id)

    def test_fallback_repository_uses_csv_when_primary_fails(self) -> None:
        primary = MagicMock()
        primary.get_claim.side_effect = ClaimsRepositoryError("offline")

        claim = FallbackClaimsRepository(
            primary,
            CsvClaimsRepository(),
        ).get_claim("CLM000377")

        self.assertIsNotNone(claim)

    def test_factory_uses_csv_when_bigquery_client_cannot_initialize(self) -> None:
        with patch(
            "src.clients.claims.bigquery.Client",
            side_effect=RuntimeError("no credentials"),
        ):
            repository = create_claims_repository(build_test_settings())

        self.assertIsInstance(repository, CsvClaimsRepository)


if __name__ == "__main__":
    unittest.main()
