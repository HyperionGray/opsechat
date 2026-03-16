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
    get_rate_limit_decision,
    configure_rate_limit_settings,
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
    configure_rate_limit_settings()
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


def test_rate_limit_exponential_backoff_increases_on_repeated_violations():
    _clear_store()
    cfg = type(
        "Cfg",
        (),
        {
            "config": {
                "SIMPLE_CHAT_RATE_LIMITS": {
                    "dm_send": {
                        "max_requests": 1,
                        "window_seconds": 60,
                        "hourly_max_requests": 20,
                    }
                },
                "SIMPLE_CHAT_BACKOFF_POLICY": {
                    "enabled": True,
                    "base_seconds": 2,
                    "multiplier": 2,
                    "max_seconds": 60,
                },
            }
        },
    )()
    configure_rate_limit_settings(cfg)

    # First request allowed.
    first = get_rate_limit_decision("session-backoff", "dm_send")
    assert first["allowed"] is True

    # First violation.
    violation_1 = get_rate_limit_decision("session-backoff", "dm_send")
    assert violation_1["allowed"] is False
    assert violation_1["backoff_level"] == 1

    # Fast-forward the temporary block without clearing timestamps so we hit a second violation.
    with _rate_limit_lock:
        _rate_limit_store["session-backoff"]["dm_send"]["blocked_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )

    violation_2 = get_rate_limit_decision("session-backoff", "dm_send")
    assert violation_2["allowed"] is False
    assert violation_2["backoff_level"] == 2
    assert violation_2["retry_after_seconds"] >= violation_1["retry_after_seconds"]


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
