from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
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
