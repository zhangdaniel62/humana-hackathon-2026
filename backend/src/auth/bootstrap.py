"""Create the local auth database from the tracked schema and demo seed."""

from __future__ import annotations

from datetime import timedelta

from .config import AuthSettings
from .store import AuthStore


def main() -> None:
    settings = AuthSettings()
    store = AuthStore(
        settings.database_path,
        session_ttl=timedelta(hours=settings.session_ttl_hours),
    )
    store.initialize(enable_demo_seed=settings.enable_demo_seed)
    seed_status = "enabled" if settings.enable_demo_seed else "disabled"
    print(f"Initialized auth database at {settings.database_path} (demo seed {seed_status}).")


if __name__ == "__main__":
    main()
