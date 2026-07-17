"""FastAPI surface smoke test for the backend checkpoint."""

from fastapi.testclient import TestClient

from src.auth import UserRole


def test_core_http_and_voice_routes_are_available(
    configured_auth_app, login_as
) -> None:
    client = TestClient(configured_auth_app)

    health = client.get("/health")
    apps = client.get("/list-apps")
    demo = client.get("/demo/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert apps.status_code == 401
    assert demo.status_code == 401

    login_as(client, UserRole.MANAGER)
    apps = client.get("/list-apps")
    assert apps.status_code == 200
    assert "claim_assist" in apps.json()

    login_as(client, UserRole.REP)
    demo = client.get("/demo/")
    assert demo.status_code == 200
    assert "Claim Assist" in demo.text
    assert "set_mode" in demo.text
    assert str(configured_auth_app.url_path_for("voice_call")) == "/ws/voice"
    assert str(configured_auth_app.url_path_for("conversation")) == "/ws/conversation"
