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
    check_rate_limit_with_metadata,
    RATE_LIMITS,
    _rate_limit_store,
    _rate_limit_lock,
    _violation_store,
    _violation_lock,
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
    with _violation_lock:
        _violation_store.clear()


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


def test_rate_limit_returns_retry_metadata_on_block():
    _clear_store()
    sid = "session-meta"
    max_requests = RATE_LIMITS["dm_send"]["max_requests"]

    for _ in range(max_requests):
        allowed, retry_after, meta = check_rate_limit_with_metadata(sid, "dm_send")
        assert allowed is True
        assert retry_after == 0
        assert meta["suggested_backoff_seconds"] == 0

    allowed, retry_after, meta = check_rate_limit_with_metadata(sid, "dm_send")
    assert allowed is False
    assert retry_after >= 1
    assert meta["retry_after"] == retry_after
    assert meta["suggested_backoff_seconds"] >= retry_after
    assert meta["violations_in_window"] >= 1


def test_rate_limit_backoff_increases_with_repeat_violations():
    _clear_store()
    sid = "session-repeat-violations"
    max_requests = RATE_LIMITS["dm_send"]["max_requests"]

    for _ in range(max_requests):
        check_rate_limit_with_metadata(sid, "dm_send")

    _, retry_after_1, meta_1 = check_rate_limit_with_metadata(sid, "dm_send")
    _, retry_after_2, meta_2 = check_rate_limit_with_metadata(sid, "dm_send")

    assert retry_after_1 >= 1
    assert retry_after_2 >= 1
    assert meta_2["suggested_backoff_seconds"] >= meta_1["suggested_backoff_seconds"]
    assert meta_2["violations_in_window"] >= meta_1["violations_in_window"]


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
