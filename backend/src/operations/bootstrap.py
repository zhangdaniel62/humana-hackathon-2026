"""Initialize the shared local auth and synthetic operations database."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ..auth import AuthSettings, AuthStore
from .store import OperationsStore

BACKEND_DIR = Path(__file__).resolve().parents[2]


def main() -> None:
    settings = AuthSettings()
    auth_store = AuthStore(
        settings.database_path,
        session_ttl=timedelta(hours=settings.session_ttl_hours),
    )
    auth_store.initialize(enable_demo_seed=settings.enable_demo_seed)
    operations_store = OperationsStore(
        settings.database_path,
        BACKEND_DIR.parent / "datasets",
    )
    operations_store.initialize(enable_demo_seed=settings.enable_demo_seed)
    seed_status = "enabled" if settings.enable_demo_seed else "disabled"
    print(
        f"Initialized shared local database at {settings.database_path} "
        f"(demo seed {seed_status})."
    )


if __name__ == "__main__":
    main()
