"""Authentication configuration independent of Google Cloud settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import AuthUser, UserRole

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
    bypass_enabled: bool = False
    bypass_role: UserRole = UserRole.CUSTOMER
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    def bypass_user(self) -> AuthUser | None:
        """Return the configured synthetic user when local auth bypass is enabled."""

        if not self.bypass_enabled:
            return None
        return AuthUser.from_record(
            user_id=0,
            username=f"auth-bypass-{self.bypass_role.value}",
            role=self.bypass_role.value,
        )
