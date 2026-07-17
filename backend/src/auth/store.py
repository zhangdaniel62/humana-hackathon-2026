"""SQLite user and opaque-session persistence."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .models import AuthUser, UserRole, normalize_username

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_SEED_PATH = Path(__file__).with_name("demo_seed.sql")


def _timestamp(value: datetime | None = None) -> int:
    return int((value or datetime.now(UTC)).timestamp())


class AuthStore:
    """Small synchronous store; each operation uses its own SQLite connection."""

    def __init__(
        self,
        database_path: Path,
        *,
        session_ttl: timedelta = timedelta(hours=8),
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.session_ttl = session_ttl
        self.password_hasher = password_hasher or PasswordHasher()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self, *, enable_demo_seed: bool = True) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            if enable_demo_seed:
                connection.executescript(_SEED_PATH.read_text(encoding="utf-8"))
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (_timestamp(),)
            )

    def authenticate(self, username: str, password: str) -> AuthUser | None:
        normalized = normalize_username(username)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role, is_active "
                "FROM users WHERE username = ?",
                (normalized,),
            ).fetchone()
            if row is None or not row["is_active"]:
                return None
            try:
                self.password_hasher.verify(row["password_hash"], password)
            except (InvalidHashError, VerificationError, VerifyMismatchError):
                return None
            if self.password_hasher.check_needs_rehash(row["password_hash"]):
                connection.execute(
                    "UPDATE users SET password_hash = ?, updated_at = unixepoch() "
                    "WHERE id = ?",
                    (self.password_hasher.hash(password), row["id"]),
                )
            return self._to_user(row)

    def get_active_user(self, username: str) -> AuthUser | None:
        """Resolve an active user without exposing or reusing its password."""

        normalized = normalize_username(username)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, role, is_active FROM users "
                "WHERE username = ? AND is_active = 1",
                (normalized,),
            ).fetchone()
        return self._to_user(row) if row is not None else None

    def create_user(
        self,
        username: str,
        password: str,
        role: UserRole,
        *,
        is_active: bool = True,
    ) -> AuthUser:
        normalized = normalize_username(username)
        if not normalized:
            raise ValueError("username must not be blank")
        password_hash = self.password_hasher.hash(password)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash, role, is_active) "
                "VALUES (?, ?, ?, ?)",
                (normalized, password_hash, role.value, int(is_active)),
            )
            user_id = int(cursor.lastrowid)
        return AuthUser.from_record(
            user_id=user_id,
            username=normalized,
            role=role.value,
        )

    def create_session(
        self, user: AuthUser, *, now: datetime | None = None
    ) -> str:
        created_at = now or datetime.now(UTC)
        expires_at = created_at + self.session_ttl
        token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    self.hash_token(token),
                    user.id,
                    _timestamp(created_at),
                    _timestamp(expires_at),
                ),
            )
        return token

    def resolve_session(
        self, token: str | None, *, now: datetime | None = None
    ) -> AuthUser | None:
        if not token:
            return None
        token_hash = self.hash_token(token)
        current_timestamp = _timestamp(now)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT users.id, users.username, users.role, users.is_active, "
                "sessions.expires_at FROM sessions "
                "JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if not row["is_active"] or row["expires_at"] <= current_timestamp:
                connection.execute(
                    "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
                )
                return None
            return self._to_user(row)

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (self.hash_token(token),),
            )

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_user(row: sqlite3.Row) -> AuthUser:
        return AuthUser.from_record(
            user_id=row["id"], username=row["username"], role=row["role"]
        )
