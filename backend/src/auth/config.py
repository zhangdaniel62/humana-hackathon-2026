"""Authentication configuration independent of Google Cloud settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = BACKEND_DIR / ".env"


class AuthSettings(BaseSettings):
    """Settings for the local SQLite authentication provider."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: Path = BACKEND_DIR / ".data" / "auth.sqlite3"
    cookie_name: str = "claim_assist_session"
    cookie_secure: bool = False
    session_ttl_hours: int = Field(default=8, ge=1, le=168)
    enable_demo_seed: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )
