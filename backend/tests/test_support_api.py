"""Focused authorization, persistence, and relay tests for live support rooms."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.auth import UserRole
from src.services.session_summary import session_summary_store


def _session_cookie(app, auth_store, role: UserRole, password: str) -> str:
    user = auth_store.authenticate(role.value, password)
    assert user is not None
    token = auth_store.create_session(user)
    return f"{app.state.auth_settings.cookie_name}={token}"


def _headers(cookie: str) -> dict[str, str]:
    return {"cookie": cookie, "origin": "http://testserver"}


def _receive_type(websocket, expected: str) -> dict:
    for _ in range(10):
        payload = websocket.receive_json()
        if payload["type"] == expected:
            return payload
    raise AssertionError(f"did not receive a {expected!r} event")


def test_customer_room_queue_and_atomic_rep_claim(
    configured_auth_app, auth_store
) -> None:
    customer = auth_store.authenticate("customer", "customer-test-password")
    assert customer is not None
    session_summary_store.capture(
        {"session_id": "owned-ai-session", "auth_user_id": str(customer.id)}
    )
    customer_cookie = _session_cookie(
        configured_auth_app,
        auth_store,
        UserRole.CUSTOMER,
        "customer-test-password",
    )
    rep_cookie = _session_cookie(
        configured_auth_app, auth_store, UserRole.REP, "rep-test-password"
    )
    manager_cookie = _session_cookie(
        configured_auth_app,
        auth_store,
        UserRole.MANAGER,
        "manager-test-password",
    )
    second_rep = auth_store.create_user(
        "rep.second", "second-rep-password", UserRole.REP
    )
    second_rep_cookie = (
        f"{configured_auth_app.state.auth_settings.cookie_name}="
        f"{auth_store.create_session(second_rep)}"
    )

    try:
        with TestClient(configured_auth_app) as client:
            forbidden_source = client.post(
                "/api/support/rooms",
                headers=_headers(customer_cookie),
                json={"source_session_id": "not-owned"},
            )
            assert forbidden_source.status_code == 403

            created = client.post(
                "/api/support/rooms",
                headers=_headers(customer_cookie),
                json={"source_session_id": "owned-ai-session"},
            )
            assert created.status_code == 200
            room = created.json()
            assert room["status"] == "waiting"
            assert room["customer"]["username"] == "customer"
            assert room["source_session_id"] == "owned-ai-session"
            room_id = room["id"]

            reused = client.post(
                "/api/support/rooms",
                headers=_headers(customer_cookie),
                json={},
            )
            assert reused.json()["id"] == room_id
            assert client.get(
                "/api/support/rooms/current", headers=_headers(customer_cookie)
            ).json()["id"] == room_id

            queue = client.get(
                "/api/support/queue", headers=_headers(rep_cookie)
            )
            assert [item["id"] for item in queue.json()] == [room_id]
            assert client.get(
                "/api/support/queue", headers=_headers(customer_cookie)
            ).status_code == 403
            assert client.get(
                "/api/support/queue", headers=_headers(manager_cookie)
            ).status_code == 403

            with client.websocket_connect(
                f"/ws/support/{room_id}", headers=_headers(customer_cookie)
            ) as waiting_ws:
                assert waiting_ws.receive_json()["type"] == "snapshot"
                _receive_type(waiting_ws, "presence")
                waiting_ws.send_json(
                    {
                        "type": "text",
                        "client_message_id": "too-early",
                        "text": "Is anyone there?",
                    }
                )
                waiting_error = _receive_type(waiting_ws, "error")
                assert waiting_error["code"] == "room_not_active"

            claimed = client.post(
                f"/api/support/rooms/{room_id}/claim",
                headers=_headers(rep_cookie),
            )
            assert claimed.status_code == 200
            assert claimed.json()["status"] == "active"
            assert claimed.json()["assigned_rep"]["username"] == "rep"

            lost_race = client.post(
                f"/api/support/rooms/{room_id}/claim",
                headers=_headers(second_rep_cookie),
            )
            assert lost_race.status_code == 409
            wrong_rep_complete = client.post(
                f"/api/support/rooms/{room_id}/complete",
                headers=_headers(second_rep_cookie),
            )
            assert wrong_rep_complete.status_code == 409

            completed = client.post(
                f"/api/support/rooms/{room_id}/complete",
                headers=_headers(rep_cookie),
            )
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert completed.json()["completed_at"] is not None
            assert (
                client.get(
                    "/api/support/rooms/current", headers=_headers(customer_cookie)
                ).json()
                is None
            )
    finally:
        session_summary_store.clear()


def test_support_websocket_relays_text_and_bidirectional_pcm16(
    configured_auth_app, auth_store
) -> None:
    customer_cookie = _session_cookie(
        configured_auth_app,
        auth_store,
        UserRole.CUSTOMER,
        "customer-test-password",
    )
    rep_cookie = _session_cookie(
        configured_auth_app, auth_store, UserRole.REP, "rep-test-password"
    )

    with TestClient(configured_auth_app) as client:
        room = client.post(
            "/api/support/rooms", headers=_headers(customer_cookie), json={}
        ).json()
        room_id = room["id"]
        assert client.post(
            f"/api/support/rooms/{room_id}/claim", headers=_headers(rep_cookie)
        ).status_code == 200

        with client.websocket_connect(
            f"/ws/support/{room_id}", headers=_headers(customer_cookie)
        ) as customer_ws:
            customer_snapshot = customer_ws.receive_json()
            assert customer_snapshot["type"] == "snapshot"
            assert customer_snapshot["messages"] == []
            assert customer_snapshot["presence"] == {
                "customer": True,
                "rep": False,
            }
            _receive_type(customer_ws, "presence")

            with client.websocket_connect(
                f"/ws/support/{room_id}", headers=_headers(rep_cookie)
            ) as rep_ws:
                rep_snapshot = rep_ws.receive_json()
                assert rep_snapshot["type"] == "snapshot"
                assert rep_snapshot["presence"] == {"customer": True, "rep": True}
                _receive_type(rep_ws, "presence")
                _receive_type(customer_ws, "presence")

                customer_ws.send_json(
                    {
                        "type": "text",
                        "client_message_id": "customer-message-1",
                        "text": "I need help with my claim",
                    }
                )
                customer_text = _receive_type(customer_ws, "text")["message"]
                rep_text = _receive_type(rep_ws, "text")["message"]
                assert customer_text == rep_text
                assert rep_text["sender"]["role"] == "customer"
                assert rep_text["text"] == "I need help with my claim"

                # The same client id from the same sender is acknowledged but
                # does not create or rebroadcast a second durable message.
                customer_ws.send_json(
                    {
                        "type": "text",
                        "client_message_id": "customer-message-1",
                        "text": "changed retry text",
                    }
                )
                deduped = _receive_type(customer_ws, "text")["message"]
                assert deduped["id"] == customer_text["id"]
                assert deduped["text"] == "I need help with my claim"

                rep_ws.send_json(
                    {
                        "type": "text",
                        "client_message_id": "rep-message-1",
                        "text": "I can help",
                    }
                )
                customer_reply = _receive_type(customer_ws, "text")["message"]
                rep_reply = _receive_type(rep_ws, "text")["message"]
                assert customer_reply == rep_reply
                assert customer_reply["sender"]["role"] == "rep"

                customer_ws.send_json({"type": "set_voice", "enabled": True})
                _receive_type(customer_ws, "presence")
                _receive_type(rep_ws, "presence")
                rep_ws.send_json({"type": "set_voice", "enabled": True})
                customer_presence = _receive_type(customer_ws, "presence")
                rep_presence = _receive_type(rep_ws, "presence")
                assert customer_presence["voice"] == rep_presence["voice"] == {
                    "customer_enabled": True,
                    "rep_enabled": True,
                }

                customer_audio = b"\x00\x01" * 160
                customer_ws.send_bytes(customer_audio)
                assert rep_ws.receive_bytes() == customer_audio

                rep_audio = b"\x02\x03" * 160
                rep_ws.send_bytes(rep_audio)
                assert customer_ws.receive_bytes() == rep_audio

        messages = configured_auth_app.state.support_store.list_messages(room_id)
        assert [(item.sender.role, item.text) for item in messages] == [
            (UserRole.CUSTOMER, "I need help with my claim"),
            (UserRole.REP, "I can help"),
        ]
