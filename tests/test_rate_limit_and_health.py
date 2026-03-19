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
    RATE_LIMITS,
    _rate_limit_store,
    _rate_limit_backoff_store,
    _rate_limit_lock,
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
        _rate_limit_backoff_store.clear()


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


def test_rate_limit_backoff_increases_for_repeat_violations():
    _clear_store()
    sid = "session-backoff"
    endpoint = "test_backoff_endpoint"
    original_config = RATE_LIMITS.get(endpoint)
    RATE_LIMITS[endpoint] = {
        "max_requests": 1,
        "window_seconds": 1,
        "backoff_base_seconds": 2,
        "backoff_max_seconds": 32,
        "violation_reset_seconds": 120,
    }
    try:
        allowed, retry_after = check_rate_limit(sid, endpoint)
        assert allowed is True
        assert retry_after == 0

        allowed, retry_after_1 = check_rate_limit(sid, endpoint)
        assert allowed is False
        assert retry_after_1 >= 2

        # Force the active backoff to expire so we can trigger a second violation
        # immediately and verify the exponential increase.
        with _rate_limit_lock:
            _rate_limit_backoff_store[sid][endpoint]["blocked_until"] = (
                datetime.datetime.now() - datetime.timedelta(seconds=1)
            )
            _rate_limit_store[sid][endpoint] = [datetime.datetime.now()]

        allowed, retry_after_2 = check_rate_limit(sid, endpoint)
        assert allowed is False
        assert retry_after_2 >= 4
        assert retry_after_2 > retry_after_1
    finally:
        if original_config is None:
            del RATE_LIMITS[endpoint]
        else:
            RATE_LIMITS[endpoint] = original_config


def test_rate_limited_endpoint_returns_retry_after_header():
    _clear_store()
    client = _test_app.test_client()

    create_resp = client.post("/chat/create", content_type="application/json")
    assert create_resp.status_code == 200
    room_id = create_resp.get_json()["room_id"]

    for i in range(30):
        resp = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": f"message {i}"},
        )
        assert resp.status_code == 200

    blocked = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": "blocked"},
    )
    assert blocked.status_code == 429
    payload = blocked.get_json()
    assert payload is not None
    assert "retry_after_seconds" in payload
    assert payload["retry_after_seconds"] >= 1
    assert payload.get("retry_strategy") == "exponential_backoff"
    assert blocked.headers.get("Retry-After") == str(payload["retry_after_seconds"])


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
    assert "active_rooms" in data


def test_health_endpoint_active_rooms_is_integer():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["active_rooms"], int)
    assert data["active_rooms"] >= 0
