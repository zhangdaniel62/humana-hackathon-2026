"""Application-scoped Sentinel, projections, dashboard, and golden-path tests."""

from fastapi.testclient import TestClient

from main import app, sentinel
from src.auth import UserRole
from src.models import EventType
from src.services.session_summary import session_summary_store


def test_operational_lifecycle_apis_and_golden_path(
    configured_auth_app, login_as
) -> None:
    assert sentinel._consumer_task is None
    with TestClient(configured_auth_app) as client:
        login_as(client, UserRole.MANAGER)
        assert sentinel._consumer_task is not None

        first = client.post("/api/demo/golden-path")
        second = client.post("/api/demo/golden-path")

        assert first.status_code == 200
        assert second.status_code == 200
        payload = first.json()
        assert payload["status"] == "complete"
        assert payload["fixed_ids"] == second.json()["fixed_ids"]
        assert payload["notification_preview"]["delivery_status"] == "not_sent"
        assert payload["intervention"]["status"] == "recorded"

        metrics = client.get("/api/metrics")
        alerts = client.get("/api/alerts")
        events = client.get("/api/events?limit=1000")
        summary = client.get("/api/sessions/golden-path-session/summary")
        dashboard = client.get("/operations")

        assert metrics.status_code == 200
        assert metrics.json()["at_risk_claims_identified"] >= 1
        assert metrics.json()["corrective_interventions_recorded"] >= 1
        assert metrics.json()["baseline"]["data_label"] == "synthetic_demo_assumption"
        assert alerts.status_code == 200
        assert any(alert["evidence_event_ids"] for alert in alerts.json())
        event_types = {event["event_type"] for event in events.json()}
        assert {
            EventType.SESSION_STARTED.value,
            EventType.DENIAL_EXPLAINED.value,
            EventType.COVERAGE_QUESTION_ANSWERED.value,
            EventType.DENIAL_RISK_DETECTED.value,
            EventType.INTERVENTION_RECOMMENDED.value,
            EventType.INTERVENTION_RECORDED.value,
            EventType.SESSION_COMPLETED.value,
        } <= event_types
        assert summary.status_code == 200
        assert summary.json()["status"] == "ready"
        assert summary.json()["notification_preview"]["delivery_status"] == "not_sent"
        assert dashboard.status_code == 200
        assert "Corrective interventions recorded" in dashboard.text

    assert sentinel._consumer_task is None


def test_session_summary_not_found(configured_auth_app, login_as) -> None:
    with TestClient(configured_auth_app) as client:
        login_as(client, UserRole.MANAGER)
        response = client.get("/api/sessions/does-not-exist/summary")

    assert response.status_code == 404


def test_session_summary_reports_incomplete_findings(
    configured_auth_app, login_as
) -> None:
    session_summary_store.capture(
        {
            "session_id": "partial-session",
            "caller_name": "Synthetic Caller",
            "roi_finding": {"status": "verified"},
        }
    )
    with TestClient(configured_auth_app) as client:
        login_as(client, UserRole.MANAGER)
        response = client.get("/api/sessions/partial-session/summary")

    assert response.status_code == 200
    assert response.json()["status"] == "incomplete"
    assert response.json()["missing_findings"] == [
        "claim",
        "benefits",
        "readiness",
    ]
