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
    get_rate_limit_headers,
    RATE_LIMITS,
    BACKOFF_CONFIG,
    _calculate_backoff_seconds,
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


def test_rate_limit_headers_report_remaining_budget():
    _clear_store()
    sid = "session-header"

    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is True
    assert retry_after == 0

    headers = get_rate_limit_headers(sid, "dm_send")
    assert headers["X-RateLimit-Limit"] == str(RATE_LIMITS["dm_send"]["max_requests"])
    assert headers["X-RateLimit-Remaining"] == str(RATE_LIMITS["dm_send"]["max_requests"] - 1)
    assert "Retry-After" not in headers


def test_rate_limit_headers_include_retry_after_when_blocked():
    _clear_store()
    sid = "session-header-blocked"
    limit = RATE_LIMITS["dm_send"]["max_requests"]

    for _ in range(limit):
        allowed, _ = check_rate_limit(sid, "dm_send")
        assert allowed is True

    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after >= 1

    headers = get_rate_limit_headers(sid, "dm_send", retry_after=retry_after)
    assert headers["Retry-After"] == str(retry_after)
    assert headers["X-RateLimit-Remaining"] == "0"


def test_backoff_calculation_doubles_until_cap():
    base = BACKOFF_CONFIG["base_seconds"]
    max_seconds = BACKOFF_CONFIG["max_seconds"]

    assert _calculate_backoff_seconds(1) == base
    assert _calculate_backoff_seconds(2) == min(base * 2, max_seconds)
    assert _calculate_backoff_seconds(3) == min(base * 4, max_seconds)
    assert _calculate_backoff_seconds(100) == max_seconds


def test_rate_limit_violation_counter_increments_for_repeated_abuse():
    _clear_store()
    sid = "session-repeat-abuse"
    endpoint = "dm_send"
    limit = RATE_LIMITS[endpoint]["max_requests"]

    for _ in range(limit):
        check_rate_limit(sid, endpoint)

    allowed, _ = check_rate_limit(sid, endpoint)
    assert allowed is False

    with _rate_limit_lock:
        first_state = _rate_limit_backoff_store[sid][endpoint].copy()
        # Simulate waiting out active lockout while still over budget in same window.
        _rate_limit_backoff_store[sid][endpoint]["blocked_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )
        _rate_limit_store[sid][endpoint] = [datetime.datetime.now()] * limit

    allowed, _ = check_rate_limit(sid, endpoint)
    assert allowed is False

    with _rate_limit_lock:
        second_state = _rate_limit_backoff_store[sid][endpoint].copy()

    assert second_state["violations"] == first_state["violations"] + 1


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
