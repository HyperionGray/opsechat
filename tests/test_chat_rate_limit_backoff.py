"""
Tests for structured rate-limit retry/backoff responses.
"""

import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import (
    _rate_limit_store,
    _rate_limit_lock,
    chat_rooms,
    rooms_lock,
)


def _reset_chat_state():
    """Reset shared in-memory state used by chat tests."""
    with _rate_limit_lock:
        _rate_limit_store.clear()
    with rooms_lock:
        chat_rooms.clear()


def test_rate_limit_policy_endpoint_returns_backoff_metadata():
    _reset_chat_state()
    client = create_app().test_client()

    response = client.get("/chat/rate-limits")
    assert response.status_code == 200

    data = response.get_json()
    assert "endpoints" in data
    assert "chat_create" in data["endpoints"]
    assert "chat_message" in data["endpoints"]
    assert "dm_send" in data["endpoints"]

    chat_create_policy = data["endpoints"]["chat_create"]
    assert chat_create_policy["max_requests"] == 3
    assert chat_create_policy["window_seconds"] == 60
    assert chat_create_policy["backoff"]["strategy"] == "exponential_full_jitter"
    assert chat_create_policy["backoff"]["base_delay_seconds"] == 1
    assert chat_create_policy["backoff"]["max_retries"] == 4


def test_chat_create_rate_limit_returns_retry_headers_and_json():
    _reset_chat_state()
    client = create_app().test_client()

    for _ in range(3):
        response = client.post("/chat/create")
        assert response.status_code == 200

    blocked = client.post("/chat/create")
    assert blocked.status_code == 429

    body = blocked.get_json()
    assert body["endpoint"] == "chat_create"
    assert body["retry_after_seconds"] >= 1
    assert body["max_requests"] == 3
    assert body["window_seconds"] == 60
    assert "backoff" in body

    assert blocked.headers["Retry-After"] == str(body["retry_after_seconds"])
    assert blocked.headers["X-RateLimit-Endpoint"] == "chat_create"
    assert blocked.headers["X-RateLimit-Limit"] == "3"
    assert blocked.headers["X-RateLimit-Window"] == "60"


def test_chat_message_rate_limit_returns_retry_headers_and_json():
    _reset_chat_state()
    client = create_app().test_client()

    create_response = client.post("/chat/create")
    assert create_response.status_code == 200
    room_id = create_response.get_json()["room_id"]

    for _ in range(30):
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "test message"},
        )
        assert response.status_code == 200

    blocked = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": "test message"},
    )
    assert blocked.status_code == 429

    body = blocked.get_json()
    assert body["endpoint"] == "chat_message"
    assert body["retry_after_seconds"] >= 1
    assert body["max_requests"] == 30
    assert body["window_seconds"] == 60
    assert body["backoff"]["strategy"] == "exponential_full_jitter"

    assert blocked.headers["Retry-After"] == str(body["retry_after_seconds"])
    assert blocked.headers["X-RateLimit-Endpoint"] == "chat_message"
    assert blocked.headers["X-RateLimit-Limit"] == "30"
    assert blocked.headers["X-RateLimit-Window"] == "60"
