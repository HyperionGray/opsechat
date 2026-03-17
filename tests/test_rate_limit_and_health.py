"""
Tests for rate limiting (simple_chat_routes) and the /health endpoint (app_factory).
"""

import datetime
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import (
    check_rate_limit,
    _rate_limit_store,
    _rate_limit_lock,
    _rate_limit_penalties,
    RATE_LIMITS,
)

# Shared test Flask app (avoids importing all of runserver.py)
_test_app = create_app()


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------

def _clear_store():
    """Helper: wipe the rate limit store between tests."""
    with _rate_limit_lock:
        _rate_limit_store.clear()
        _rate_limit_penalties.clear()


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


def test_rate_limit_backoff_increases_for_repeated_violations():
    _clear_store()
    sid = "session-backoff"
    endpoint = "dm_send"
    max_requests = RATE_LIMITS[endpoint]["max_requests"]

    for _ in range(max_requests):
        allowed, _ = check_rate_limit(sid, endpoint)
        assert allowed is True

    # Set timestamps close to window expiry so backoff controls retry_after.
    with _rate_limit_lock:
        _rate_limit_store[sid][endpoint] = [
            datetime.datetime.now() - datetime.timedelta(seconds=59)
        ] * max_requests

    allowed, retry_first = check_rate_limit(sid, endpoint)
    assert allowed is False
    assert retry_first >= 1

    # Force unblock while keeping over-limit timestamps to trigger another violation.
    with _rate_limit_lock:
        _rate_limit_penalties[sid][endpoint]["blocked_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )

    allowed, retry_second = check_rate_limit(sid, endpoint)
    assert allowed is False
    assert retry_second > retry_first


def test_messages_endpoint_returns_retry_after_header_when_throttled():
    _clear_store()
    client = create_app().test_client()

    create_room = client.post("/chat/create", content_type="application/json")
    assert create_room.status_code == 200
    room_id = create_room.get_json()["room_id"]

    message_url = f"/chat/room/{room_id}/messages"
    payload = {"message": "hello world"}

    for _ in range(30):
        response = client.post(message_url, json=payload)
        assert response.status_code == 200

    throttled = client.post(message_url, json=payload)
    assert throttled.status_code == 429
    body = throttled.get_json()
    assert body["retry_after"] >= 1
    assert throttled.headers.get("Retry-After") == str(body["retry_after"])


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
    assert "tor_connection" in data["checks"]
    assert "memory_usage" in data["checks"]
    assert "disk_space" in data["checks"]


def test_health_endpoint_checks_are_strings():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["checks"], dict)
    assert isinstance(data["checks"]["memory_usage"], str)
    assert isinstance(data["checks"]["disk_space"], str)
