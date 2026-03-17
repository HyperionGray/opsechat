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
    load_rate_limit_settings,
    _rate_limit_store,
    _rate_limit_penalties,
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


def test_rate_limit_repeated_violations_increase_backoff():
    _clear_store()
    sid = "session-backoff"

    # First violation
    for _ in range(5):
        check_rate_limit(sid, "dm_send")
    allowed, retry_after_first = check_rate_limit(sid, "dm_send")
    assert allowed is False

    # Force the temporary block to expire while keeping request history in-window.
    with _rate_limit_lock:
        _rate_limit_penalties[sid]["dm_send"]["blocked_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )

    # Second violation should carry a stronger penalty than the first.
    allowed, retry_after_second = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after_second > retry_after_first


def test_load_rate_limit_settings_from_env_values():
    env = {
        "OPSECHAT_CHAT_CREATE_MAX_REQUESTS": "12",
        "OPSECHAT_CHAT_CREATE_WINDOW_SECONDS": "90",
        "OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS": "45",
        "OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS": "120",
        "OPSECHAT_DM_SEND_MAX_REQUESTS": "7",
        "OPSECHAT_DM_SEND_WINDOW_SECONDS": "75",
        "OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS": "8",
        "OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS": "144",
    }
    limits, backoff_base, backoff_max = load_rate_limit_settings(env)

    assert limits["chat_create"]["max_requests"] == 12
    assert limits["chat_create"]["window_seconds"] == 90
    assert limits["chat_message"]["max_requests"] == 45
    assert limits["chat_message"]["window_seconds"] == 120
    assert limits["dm_send"]["max_requests"] == 7
    assert limits["dm_send"]["window_seconds"] == 75
    assert backoff_base == 8
    assert backoff_max == 144


def test_load_rate_limit_settings_invalid_values_fall_back():
    env = {
        "OPSECHAT_CHAT_CREATE_MAX_REQUESTS": "invalid",
        "OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS": "0",  # minimum should clamp to 1
        "OPSECHAT_RATE_LIMIT_BACKOFF_BASE_SECONDS": "abc",
        "OPSECHAT_RATE_LIMIT_BACKOFF_MAX_SECONDS": "2",  # should be clamped >= base
    }
    limits, backoff_base, backoff_max = load_rate_limit_settings(env)

    assert limits["chat_create"]["max_requests"] == 10
    assert limits["chat_message"]["window_seconds"] == 1
    assert backoff_base == 5
    assert backoff_max == 5


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
