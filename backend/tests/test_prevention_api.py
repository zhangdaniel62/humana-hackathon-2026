"""Role and assignment enforcement for proactive-workflow endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.auth import UserRole


def test_scan_and_queue_role_matrix(configured_auth_app, login_as) -> None:
    with TestClient(configured_auth_app) as client:
        assert client.get("/api/rep/work-items").status_code == 401
        login_as(client, UserRole.CUSTOMER)
        assert client.get("/api/rep/work-items").status_code == 403
        assert client.post(
            "/api/prevention/scans", json={"idempotency_key": "api-scan"}
        ).status_code == 403

        login_as(client, UserRole.MANAGER)
        scan = client.post(
            "/api/prevention/scans", json={"idempotency_key": "api-scan"}
        )
        assert scan.status_code == 200
        assert scan.json()["source"] == "manager"
        assert client.get("/api/rep/work-items").status_code == 403
        readiness = client.get("/api/runtime/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "ready"
        traces = client.get("/api/delegation/traces")
        assert traces.status_code == 200
        assert traces.json() == []

        login_as(client, UserRole.REP)
        assert client.get("/api/delegation/traces").status_code == 403
        queue = client.get("/api/rep/work-items")
        assert queue.status_code == 200
        missing = client.post(
            "/api/rep/work-items/does-not-exist/claim",
            json={"expected_version": 1},
        )
        assert missing.status_code == 404
        item = queue.json()["items"][0]
        assert set(item) == {
            "work_item_id",
            "claim_id",
            "rule_id",
            "title",
            "recommended_action",
            "risk_band",
            "priority_score",
            "status",
            "assigned_to",
            "version",
            "created_at",
            "updated_at",
        }
        claimed = client.post(
            f"/api/rep/work-items/{item['work_item_id']}/claim",
            json={"expected_version": item["version"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["status"] == "claimed"
        stale = client.post(
            f"/api/rep/work-items/{item['work_item_id']}/resolve",
            json={"expected_version": item["version"]},
        )
        assert stale.status_code == 409


def test_only_assignee_can_resolve_claimed_item(configured_auth_app, login_as) -> None:
    other = configured_auth_app.state.auth_store.create_user(
        "rep.other", "other-password", UserRole.REP
    )
    assert other.id > 0
    with TestClient(configured_auth_app) as client:
        login_as(client, UserRole.REP)
        item = client.get("/api/rep/work-items").json()["items"][0]
        claimed = client.post(
            f"/api/rep/work-items/{item['work_item_id']}/claim",
            json={"expected_version": item["version"]},
        ).json()
        client.post("/api/auth/logout")
        login = client.post(
            "/api/auth/login",
            json={"username": "rep.other", "password": "other-password"},
        )
        assert login.status_code == 200
        denied = client.post(
            f"/api/rep/work-items/{item['work_item_id']}/resolve",
            json={"expected_version": claimed["version"]},
        )
        assert denied.status_code == 409
