"""FastAPI surface smoke test for the backend checkpoint."""

from fastapi.testclient import TestClient

from main import app


def test_core_http_and_voice_routes_are_available() -> None:
    client = TestClient(app)

    health = client.get("/health")
    apps = client.get("/list-apps")
    demo = client.get("/demo/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert apps.status_code == 200
    assert "claim_assist" in apps.json()
    assert demo.status_code == 200
    assert "Claim Assist" in demo.text
    assert "set_mode" in demo.text
    assert str(app.url_path_for("voice_call")) == "/ws/voice"
    assert str(app.url_path_for("conversation")) == "/ws/conversation"
