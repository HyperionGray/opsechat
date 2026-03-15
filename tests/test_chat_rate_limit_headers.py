"""
Tests for chat rate-limit response headers and policy discovery endpoint.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import _rate_limit_store, _rate_limit_lock


def _clear_rate_limit_store():
    with _rate_limit_lock:
        _rate_limit_store.clear()


def _create_room(client):
    response = client.post("/chat/create", content_type="application/json")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload and payload.get("room_id")
    return payload["room_id"]


def test_chat_message_success_includes_rate_limit_headers():
    _clear_rate_limit_store()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        room_id = _create_room(client)
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "hello world"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Limit") == "30"
        assert response.headers.get("X-RateLimit-Remaining") == "29"
        assert response.headers.get("X-RateLimit-Window") == "60"
        assert response.headers.get("X-RateLimit-Reset") is not None
        assert response.headers.get("Retry-After") is None


def test_chat_message_limit_exceeded_returns_retry_after_and_metadata():
    _clear_rate_limit_store()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        room_id = _create_room(client)

        for _ in range(30):
            ok_response = client.post(
                f"/chat/room/{room_id}/messages",
                json={"message": "message within limits"},
            )
            assert ok_response.status_code == 200

        blocked = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "one too many"},
        )

        assert blocked.status_code == 429
        payload = blocked.get_json()
        assert payload is not None
        assert "rate_limit" in payload
        assert payload["rate_limit"]["limit"] == 30
        assert payload["rate_limit"]["remaining"] == 0
        assert payload["rate_limit"]["retry_after"] >= 1
        assert blocked.headers.get("X-RateLimit-Limit") == "30"
        assert blocked.headers.get("X-RateLimit-Remaining") == "0"
        assert blocked.headers.get("Retry-After") is not None
        assert int(blocked.headers["Retry-After"]) >= 1


def test_chat_rate_limit_policy_endpoint_returns_expected_defaults():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/chat/rate-limits")
        assert response.status_code == 200
        payload = response.get_json()

        assert payload is not None
        assert payload["limits"]["chat_create"]["max_requests"] == 10
        assert payload["limits"]["chat_message"]["max_requests"] == 30
        assert payload["limits"]["dm_send"]["max_requests"] == 5
        assert payload["max_message_length"] == 500
        assert payload["max_dm_length"] == 200
