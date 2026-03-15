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


def test_rate_limit_legacy_list_entries_are_supported():
    _clear_store()
    sid = "session-legacy"
    with _rate_limit_lock:
        _rate_limit_store[sid] = {
            "dm_send": [datetime.datetime.now() - datetime.timedelta(seconds=120)] * 5
        }

    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is True
    assert retry_after == 0

    with _rate_limit_lock:
        assert isinstance(_rate_limit_store[sid]["dm_send"], dict)
        assert "requests" in _rate_limit_store[sid]["dm_send"]


def test_rate_limit_backoff_escalates_on_repeated_bursts():
    _clear_store()
    endpoint = "test_backoff"
    RATE_LIMITS[endpoint] = {
        "max_requests": 1,
        "window_seconds": 1,
        "backoff_base_seconds": 2,
        "backoff_max_seconds": 8,
    }
    sid = "session-backoff"

    try:
        allowed, retry_after = check_rate_limit(sid, endpoint)
        assert allowed is True
        assert retry_after == 0

        # First violation: should apply initial backoff.
        allowed, first_retry = check_rate_limit(sid, endpoint)
        assert allowed is False
        assert first_retry >= 2

        # While blocked, request remains blocked without creating a new strike.
        allowed, blocked_retry = check_rate_limit(sid, endpoint)
        assert allowed is False
        assert blocked_retry >= 1

        # Force cooldown expiry while keeping request in-window so we hit
        # the limiter again and trigger a second strike.
        with _rate_limit_lock:
            entry = _rate_limit_store[sid][endpoint]
            entry["blocked_until"] = datetime.datetime.now() - datetime.timedelta(seconds=1)
            entry["requests"] = [datetime.datetime.now()]

        allowed, second_retry = check_rate_limit(sid, endpoint)
        assert allowed is False
        assert second_retry >= 4
        assert second_retry >= first_retry
    finally:
        RATE_LIMITS.pop(endpoint, None)


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
