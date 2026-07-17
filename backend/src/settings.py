"""Application configuration loaded from environment variables and ``.env``."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# google-genai (used inside ADK) reads GOOGLE_GENAI_USE_VERTEXAI /
# GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION from os.environ, not from
# this Settings object, so the .env values must also be exported.
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """Settings required to connect to Google Cloud and Vertex AI services."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_cloud_project: str
    google_cloud_location: str = "us"
    google_genai_use_vertexai: bool = True
    model_name: str = "gemini-3.5-flash"
    live_model_name: str = "gemini-live-2.5-flash-native-audio"
    live_model_location: str = "us-central1"
    live_voice_name: str = "Aoede"

    bigquery_dataset: str = "humana_hackathon"
    bigquery_location: str = "US"

    # Table names within the dataset (mirror the CSV file names in datasets/).
    members_table: str = "members"
    roi_authorizations_table: str = "roi_authorizations"

    gcs_bucket: str | None = None

    def table(self, name: str) -> str:
        """Fully-qualified BigQuery table id: ``project.dataset.table``."""
        return f"{self.google_cloud_project}.{self.bigquery_dataset}.{name}"


class SentinelSettings(BaseSettings):
    """Thresholds and windows used by the Sentinel event consumer."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    denial_spike_threshold: int = Field(default=3, ge=2)
    denial_window_hours: int = Field(default=24, ge=1)
    roi_gap_threshold: int = Field(default=3, ge=2)
    roi_gap_rate_threshold: float = Field(default=0.25, ge=0, le=1)
    roi_minimum_sessions: int = Field(default=5, ge=1)
    roi_window_hours: int = Field(default=24, ge=1)
    repeat_contact_days: int = Field(default=7, ge=1)
    evidence_limit: int = Field(default=25, ge=1, le=100)


settings = Settings()
