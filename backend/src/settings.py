"""Application configuration loaded from environment variables and ``.env``."""

from pathlib import Path

from dotenv import load_dotenv
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

    gcs_bucket: str

    def table(self, name: str) -> str:
        """Fully-qualified BigQuery table id: ``project.dataset.table``."""
        return f"{self.google_cloud_project}.{self.bigquery_dataset}.{name}"


settings = Settings()
