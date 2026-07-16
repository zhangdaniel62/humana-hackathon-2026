"""Configuration. Single BaseSettings, singleton instance, injectable for tests."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DataSource = Literal["csv", "bigquery"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BENEFITS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Where coverage_rules / members / providers come from. CSV is the default
    #: because it needs no credentials and cannot fail on demo day.
    data_source: DataSource = "csv"

    #: When data_source is "bigquery" and BigQuery is unreachable, fall back to
    #: the CSVs rather than failing the request. The CSVs are the same data, so
    #: the answer stays correct; the source actually used is reported on every
    #: answer via BenefitsAnswer.data_source. Set False to fail loudly instead.
    bigquery_fallback_to_csv: bool = True

    bq_project: str | None = None
    bq_dataset: str | None = None
    bq_location: str | None = None

    #: Table names, in case they differ from the CSV basenames.
    bq_coverage_rules_table: str = "coverage_rules"
    bq_members_table: str = "members"
    bq_providers_table: str = "providers"

    datasets_dir: Path = Field(default=_REPO_ROOT / "datasets")

    model: str = "gemini-flash-latest"

    @model_validator(mode="after")
    def _require_bq_config(self) -> "Settings":
        if self.data_source == "bigquery" and not (self.bq_project and self.bq_dataset):
            raise ValueError(
                "data_source='bigquery' requires BENEFITS_BQ_PROJECT and "
                "BENEFITS_BQ_DATASET to be set."
            )
        return self

    def table_ref(self, table: str) -> str:
        return f"{self.bq_project}.{self.bq_dataset}.{table}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton. Pass an explicit Settings to inject in tests."""
    return Settings()


def reset_settings_cache() -> None:
    """For tests that mutate the environment."""
    get_settings.cache_clear()
