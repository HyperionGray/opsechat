"""
Tests for rate limiting (simple_chat_routes) and the /health endpoint (app_factory).
"""

import datetime
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import check_rate_limit, _rate_limit_store, _rate_limit_lock

# Shared test Flask app (avoids importing all of runserver.py)
_test_app = create_app()


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------

def _clear_store():
    """Helper: wipe the rate limit store between tests."""
    with _rate_limit_lock:
        _rate_limit_store.clear()


def test_rate_limit_allows_requests_within_window():
    _clear_store()
    for _ in range(5):
        allowed, retry_after = check_rate_limit("session-1", "dm_send")
        assert allowed is True
        assert retry_after == 0


def test_rate_limit_blocks_when_exceeded():
    _clear_store()
    # dm_send: 5 requests per 60 seconds
    for _ in range(5):
        check_rate_limit("session-block", "dm_send")
    allowed, retry_after = check_rate_limit("session-block", "dm_send")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_tracks_sessions_independently():
    _clear_store()
    # Exhaust session-a
    for _ in range(5):
        check_rate_limit("session-a", "dm_send")
    # session-b should still be allowed
    allowed, _ = check_rate_limit("session-b", "dm_send")
    assert allowed is True


def test_rate_limit_resets_after_window():
    _clear_store()
    sid = "session-expire"
    # Backdate all existing timestamps so they fall outside the window
    with _rate_limit_lock:
        _rate_limit_store[sid] = {
            "dm_send": [
                datetime.datetime.now() - datetime.timedelta(seconds=120)
            ] * 5
        }
    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is True
    assert retry_after == 0


def test_rate_limit_unknown_endpoint_always_allows():
    _clear_store()
    for _ in range(100):
        allowed, _ = check_rate_limit("session-x", "nonexistent_endpoint")
        assert allowed is True


def test_rate_limit_chat_message_limit():
    _clear_store()
    # chat_message: 30 requests per 60 seconds
    for _ in range(30):
        allowed, _ = check_rate_limit("session-msg", "chat_message")
        assert allowed is True
    allowed, retry_after = check_rate_limit("session-msg", "chat_message")
    assert allowed is False
    assert retry_after >= 1


# ---------------------------------------------------------------------------
# Health endpoint integration tests
# ---------------------------------------------------------------------------

def test_health_endpoint_returns_200():
    client = _test_app.test_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_json_with_required_fields():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert data is not None
    assert data.get("status") == "healthy"
    assert "version" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)
    assert {"tor_connection", "memory_usage", "disk_space"}.issubset(set(data["checks"].keys()))


def test_health_endpoint_uptime_seconds_is_non_negative_number():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_chat_create_429_includes_retry_metadata():
    client = _test_app.test_client()

    for _ in range(3):
        response = client.post("/chat/create", json={})
        assert response.status_code == 200

    blocked = client.post("/chat/create", json={})
    assert blocked.status_code == 429

    payload = blocked.get_json()
    assert payload is not None
    assert payload.get("error_code") == "rate_limit_exceeded"
    assert isinstance(payload.get("retry_after"), int)
    assert payload["retry_after"] >= 1
    assert blocked.headers.get("Retry-After") == str(payload["retry_after"])
    assert "backoff_hint" in payload


def test_chat_message_429_includes_retry_metadata():
    client = _test_app.test_client()

    create_response = client.post("/chat/create", json={})
    assert create_response.status_code == 200
    room_id = create_response.get_json()["room_id"]

    for _ in range(30):
        send_response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "hello"}
        )
        assert send_response.status_code == 200

    blocked = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": "blocked"}
    )
    assert blocked.status_code == 429

    payload = blocked.get_json()
    assert payload is not None
    assert payload.get("error_code") == "rate_limit_exceeded"
    assert isinstance(payload.get("retry_after"), int)
    assert payload["retry_after"] >= 1
    assert blocked.headers.get("Retry-After") == str(payload["retry_after"])
