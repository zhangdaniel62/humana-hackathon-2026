"""Local authentication, authorization, and session tests."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from argon2 import PasswordHasher
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from src.auth import AuthStore, UserRole
from src.events import event_log
from src.services.session_summary import session_summary_store


class _SessionService:
    async def create_session(self, **kwargs):
        return SimpleNamespace(id=kwargs["session_id"], state=kwargs["state"])


class _WaitingRunner:
    def __init__(self) -> None:
        self.session_service = _SessionService()

    async def run_live(self, **kwargs):
        await asyncio.Event().wait()
        if False:
            yield None


def test_tracked_demo_seed_is_idempotent_and_uses_argon2(tmp_path) -> None:
    database_path = tmp_path / "seeded.sqlite3"
    store = AuthStore(database_path)

    store.initialize(enable_demo_seed=True)
    store.initialize(enable_demo_seed=True)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT username, password_hash, role FROM users ORDER BY username"
        ).fetchall()
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert schema_version == 1
    assert [(row[0], row[2]) for row in rows] == [
        ("customer", "customer"),
        ("manager", "manager"),
        ("rep", "rep"),
        ("rep.alex", "rep"),
        ("rep.jordan", "rep"),
        ("rep.morgan", "rep"),
        ("rep.taylor", "rep"),
    ]
    assert all(row[1].startswith("$argon2id$") for row in rows)
    assert "ManagerDemo2026!" not in "".join(row[1] for row in rows)
    assert store.authenticate(" MANAGER ", "ManagerDemo2026!") is not None
    assert store.authenticate("customer", "CustomerDemo2026!") is not None
    assert store.authenticate("rep", "RepDemo2026!") is not None
    assert store.authenticate("rep.alex", "RepDemo2026!") is not None


def test_sessions_are_hashed_expire_and_can_be_revoked(tmp_path) -> None:
    store = AuthStore(
        tmp_path / "sessions.sqlite3",
        session_ttl=timedelta(hours=8),
        password_hasher=PasswordHasher(
            time_cost=1, memory_cost=8 * 1024, parallelism=1
        ),
    )
    store.initialize(enable_demo_seed=False)
    user = store.create_user("CaseFolded", "correct horse battery staple", UserRole.REP)
    store.create_user(
        "inactive",
        "inactive password",
        UserRole.CUSTOMER,
        is_active=False,
    )
    now = datetime(2026, 7, 16, 12, tzinfo=UTC)
    token = store.create_session(user, now=now)

    with sqlite3.connect(store.database_path) as connection:
        stored_token = connection.execute(
            "SELECT token_hash FROM sessions"
        ).fetchone()[0]

    assert user.username == "casefolded"
    assert store.authenticate("inactive", "inactive password") is None
    assert stored_token == store.hash_token(token)
    assert stored_token != token
    assert store.resolve_session(token, now=now + timedelta(hours=7)) == user

    store.revoke_session(token)
    assert store.resolve_session(token, now=now) is None

    expired_token = store.create_session(user, now=now)
    assert store.resolve_session(
        expired_token, now=now + timedelta(hours=8)
    ) is None


def test_login_me_logout_and_cookie_contract(configured_auth_app, login_as) -> None:
    client = TestClient(configured_auth_app)

    unknown = client.post(
        "/api/auth/login", json={"username": "missing", "password": "wrong"}
    )
    wrong_password = client.post(
        "/api/auth/login", json={"username": "customer", "password": "wrong"}
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json() == {
        "detail": "Invalid username or password"
    }

    login = login_as(client, UserRole.CUSTOMER)
    assert login.json()["user"] == {
        "id": login.json()["user"]["id"],
        "username": "customer",
        "role": "customer",
        "capabilities": ["chat", "voice"],
    }
    set_cookie = login.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "max-age=28800" in set_cookie
    assert "secure" not in set_cookie

    assert client.get("/api/auth/me").json() == login.json()
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    ("role", "metrics_status", "demo_status"),
    [
        (UserRole.MANAGER, 200, 403),
        (UserRole.CUSTOMER, 403, 200),
        (UserRole.REP, 403, 200),
    ],
)
def test_http_role_matrix(
    configured_auth_app,
    login_as,
    role: UserRole,
    metrics_status: int,
    demo_status: int,
) -> None:
    client = TestClient(configured_auth_app)
    login_as(client, role)

    assert client.get("/api/metrics").status_code == metrics_status
    assert client.get("/demo/").status_code == demo_status
    assert client.get("/list-apps").status_code == (
        200 if role is UserRole.MANAGER else 403
    )


def test_customer_summary_access_is_owner_scoped(configured_auth_app, login_as) -> None:
    client = TestClient(configured_auth_app)
    customer = login_as(client, UserRole.CUSTOMER).json()["user"]
    session_summary_store.capture(
        {
            "session_id": "owned-session",
            "auth_user_id": str(customer["id"]),
        }
    )
    session_summary_store.capture(
        {"session_id": "other-session", "auth_user_id": "someone-else"}
    )
    try:
        assert client.get("/api/sessions/owned-session/summary").status_code == 200
        assert client.get("/api/sessions/other-session/summary").status_code == 403

        login_as(client, UserRole.REP)
        assert client.get("/api/sessions/other-session/summary").status_code == 200

        login_as(client, UserRole.MANAGER)
        assert client.get("/api/sessions/other-session/summary").status_code == 200
    finally:
        session_summary_store.clear()


def test_auth_bypass_uses_configured_role_without_elevating_permissions(
    configured_auth_app,
) -> None:
    configured_auth_app.state.auth_settings = (
        configured_auth_app.state.auth_settings.model_copy(
            update={"bypass_enabled": True, "bypass_role": UserRole.CUSTOMER}
        )
    )
    client = TestClient(configured_auth_app)

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["user"] == {
        "id": 0,
        "username": "auth-bypass-customer",
        "role": "customer",
        "capabilities": ["chat", "voice"],
    }
    assert client.get("/demo/").status_code == 200
    assert client.get("/api/metrics").status_code == 403
    runner = _WaitingRunner()
    with patch("src.api.voice._get_runner", return_value=runner):
        with client.websocket_connect("/ws/conversation") as websocket:
            started = websocket.receive_json()
            assert started["type"] == "session_started"
            assert started["agent_audio_enabled"] is True
            assert session_summary_store.owner_user_id(started["session_id"]) == "0"
            websocket.close()
    session_summary_store.clear()


def test_websocket_role_and_origin_enforcement(configured_auth_app, login_as) -> None:
    event_log.clear()
    session_summary_store.clear()
    client = TestClient(configured_auth_app)
    runner = _WaitingRunner()
    try:
        login_as(client, UserRole.MANAGER)
        with pytest.raises(WebSocketDisconnect) as manager_denied:
            with client.websocket_connect("/ws/conversation"):
                pass
        assert manager_denied.value.code == 4403

        with patch("src.api.voice._get_runner", return_value=runner):
            login_as(client, UserRole.CUSTOMER)
            with client.websocket_connect("/ws/voice") as websocket:
                started = websocket.receive_json()
                assert started["type"] == "session_started"
                assert started["agent_audio_enabled"] is True
                websocket.send_json({"type": "set_mode", "mode": "voice"})
                assert websocket.receive_json() == {
                    "type": "mode_changed",
                    "mode": "voice",
                }
                websocket.close()

            with client.websocket_connect("/ws/conversation") as websocket:
                assert websocket.receive_json()["type"] == "session_started"
                websocket.send_json({"type": "set_mode", "mode": "voice"})
                assert websocket.receive_json() == {
                    "type": "mode_changed",
                    "mode": "voice",
                }
                websocket.close()

        login_as(client, UserRole.REP)
        with pytest.raises(WebSocketDisconnect) as origin_denied:
            with client.websocket_connect(
                "/ws/voice", headers={"origin": "https://evil.example"}
            ):
                pass
        assert origin_denied.value.code == 4403

        with patch("src.api.voice._get_runner", return_value=runner):
            with client.websocket_connect("/ws/voice") as websocket:
                started = websocket.receive_json()
                assert started["type"] == "session_started"
                assert started["agent_audio_enabled"] is True
                websocket.close()
    finally:
        event_log.clear()
        session_summary_store.clear()


def test_http_rejects_untrusted_browser_origin(configured_auth_app, login_as) -> None:
    client = TestClient(configured_auth_app)
    login_as(client, UserRole.MANAGER)

    response = client.get(
        "/api/metrics", headers={"origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed"}


def test_raw_adk_websocket_is_manager_only(configured_auth_app, login_as) -> None:
    client = TestClient(configured_auth_app)

    with pytest.raises(WebSocketDisconnect) as unauthenticated:
        with client.websocket_connect("/run_live"):
            pass
    assert unauthenticated.value.code == 4401

    login_as(client, UserRole.REP)
    with pytest.raises(WebSocketDisconnect) as rep_denied:
        with client.websocket_connect("/run_live"):
            pass
    assert rep_denied.value.code == 4403
