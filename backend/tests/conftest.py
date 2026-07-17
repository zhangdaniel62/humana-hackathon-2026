"""Shared isolated authentication fixtures for application tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from argon2 import PasswordHasher

from src.auth import AuthSettings, AuthStore, UserRole

TEST_PASSWORDS = {
    UserRole.MANAGER: "manager-test-password",
    UserRole.CUSTOMER: "customer-test-password",
    UserRole.REP: "rep-test-password",
}


@pytest.fixture
def auth_store(tmp_path):
    store = AuthStore(
        tmp_path / "auth.sqlite3",
        session_ttl=timedelta(hours=8),
        password_hasher=PasswordHasher(
            time_cost=1,
            memory_cost=8 * 1024,
            parallelism=1,
        ),
    )
    store.initialize(enable_demo_seed=False)
    for role, password in TEST_PASSWORDS.items():
        store.create_user(role.value, password, role)
    return store


@pytest.fixture
def configured_auth_app(auth_store):
    from main import app

    original_store = app.state.auth_store
    original_settings = app.state.auth_settings
    app.state.auth_store = auth_store
    app.state.auth_settings = AuthSettings(
        database_path=auth_store.database_path,
        enable_demo_seed=False,
        cookie_secure=False,
        allowed_origins=["http://testserver"],
    )
    try:
        yield app
    finally:
        app.state.auth_store = original_store
        app.state.auth_settings = original_settings


@pytest.fixture
def login_as():
    def login(client, role: UserRole):
        response = client.post(
            "/api/auth/login",
            json={"username": role.value, "password": TEST_PASSWORDS[role]},
        )
        assert response.status_code == 200
        return response

    return login
