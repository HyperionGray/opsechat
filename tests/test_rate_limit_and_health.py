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
    RATE_LIMITS,
    check_rate_limit,
    load_rate_limits,
    _rate_limit_store,
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


def test_load_rate_limits_uses_defaults_when_env_missing():
    config = load_rate_limits(env={})
    assert config["chat_create"]["max_requests"] == 10
    assert config["chat_create"]["window_seconds"] == 60
    assert config["chat_message"]["max_requests"] == 30
    assert config["dm_send"]["max_requests"] == 5


def test_load_rate_limits_applies_overrides_and_fallbacks():
    config = load_rate_limits(env={
        "OPSECHAT_CHAT_CREATE_MAX_REQUESTS": "12",
        "OPSECHAT_CHAT_CREATE_WINDOW_SECONDS": "90",
        "OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS": "0",  # invalid (non-positive)
        "OPSECHAT_DM_SEND_WINDOW_SECONDS": "abc",   # invalid (non-integer)
    })

    assert config["chat_create"]["max_requests"] == 12
    assert config["chat_create"]["window_seconds"] == 90
    # invalid values should fall back to defaults
    assert config["chat_message"]["max_requests"] == 30
    assert config["dm_send"]["window_seconds"] == 60


def test_rate_limited_response_has_retry_headers_and_metadata():
    _clear_store()
    original_dm_limit = RATE_LIMITS["dm_send"].copy()
    RATE_LIMITS["dm_send"] = {"max_requests": 1, "window_seconds": 60}
    try:
        with _test_app.test_client() as client:
            payload = {"room_id": "room-123", "message": "join this room"}
            first = client.post("/chat/dm/send", json=payload)
            assert first.status_code == 200

            second = client.post("/chat/dm/send", json=payload)
            assert second.status_code == 429

            data = second.get_json()
            assert data["error"] == "Rate limit exceeded"
            assert data["endpoint"] == "dm_send"
            assert data["retry_after_seconds"] >= 1
            assert data["limit"]["max_requests"] == 1
            assert data["limit"]["window_seconds"] == 60
            assert data["limit"]["remaining"] == 0
            assert second.headers.get("Retry-After") is not None
            assert second.headers.get("X-RateLimit-Limit") == "1"
    finally:
        RATE_LIMITS["dm_send"] = original_dm_limit
        _clear_store()


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
