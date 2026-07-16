"""Application configuration loaded from environment variables and ``.env``."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings required to connect to Google Cloud and Vertex AI services."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    model_name: str = "gemini-3.5-flash"

    bigquery_dataset: str = "humana_hackathon"
    bigquery_location: str = "US"

    gcs_bucket: str


settings = Settings()
