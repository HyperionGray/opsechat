"""
Tests for rate limiting (simple_chat_routes) and the /health endpoint (app_factory).
"""

import datetime
import sys
import os
from flask import Flask

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
import simple_chat_routes as scr

# Shared test Flask app (avoids importing all of runserver.py)
_test_app = create_app()


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------

def _clear_store():
    """Helper: wipe the rate limit store between tests."""
    with scr._rate_limit_lock:
        scr._rate_limit_store.clear()
        scr._rate_limit_backoff_state.clear()
    # Reset defaults/env-based config so tests are deterministic.
    scr.configure_rate_limits()


def test_rate_limit_allows_requests_within_window():
    _clear_store()
    for _ in range(5):
        allowed, retry_after = scr.check_rate_limit("session-1", "dm_send")
        assert allowed is True
        assert retry_after == 0


def test_rate_limit_blocks_when_exceeded():
    _clear_store()
    # dm_send: 5 requests per 60 seconds
    for _ in range(5):
        scr.check_rate_limit("session-block", "dm_send")
    allowed, retry_after = scr.check_rate_limit("session-block", "dm_send")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_tracks_sessions_independently():
    _clear_store()
    # Exhaust session-a
    for _ in range(5):
        scr.check_rate_limit("session-a", "dm_send")
    # session-b should still be allowed
    allowed, _ = scr.check_rate_limit("session-b", "dm_send")
    assert allowed is True


def test_rate_limit_resets_after_window():
    _clear_store()
    sid = "session-expire"
    # Backdate all existing timestamps so they fall outside the window
    with scr._rate_limit_lock:
        scr._rate_limit_store[sid] = {
            "dm_send": [
                datetime.datetime.now() - datetime.timedelta(seconds=120)
            ] * 5
        }
    allowed, retry_after = scr.check_rate_limit(sid, "dm_send")
    assert allowed is True
    assert retry_after == 0


def test_rate_limit_unknown_endpoint_always_allows():
    _clear_store()
    for _ in range(100):
        allowed, _ = scr.check_rate_limit("session-x", "nonexistent_endpoint")
        assert allowed is True


def test_rate_limit_chat_message_limit():
    _clear_store()
    # chat_message: 30 requests per 60 seconds
    for _ in range(30):
        allowed, _ = scr.check_rate_limit("session-msg", "chat_message")
        assert allowed is True
    allowed, retry_after = scr.check_rate_limit("session-msg", "chat_message")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_backoff_increases_on_repeated_violation_attempts():
    _clear_store()
    for _ in range(5):
        allowed, _ = scr.check_rate_limit("session-backoff", "dm_send")
        assert allowed is True

    allowed, retry_after_1 = scr.check_rate_limit("session-backoff", "dm_send")
    assert allowed is False
    assert retry_after_1 >= 1

    # Immediate retry while still blocked should increase penalty.
    allowed, retry_after_2 = scr.check_rate_limit("session-backoff", "dm_send")
    assert allowed is False
    assert retry_after_2 >= retry_after_1


def test_rate_limit_config_can_be_overridden_from_app_config():
    _clear_store()
    app = Flask(__name__)
    app.config["SIMPLE_CHAT_RATE_LIMITS"] = {
        "chat_create": {"max_requests": 2, "window_seconds": 30},
    }
    app.config["SIMPLE_CHAT_RATE_LIMIT_BACKOFF"] = {
        "base_seconds": 1,
        "max_seconds": 8,
    }

    scr.configure_rate_limits(app)
    assert scr.RATE_LIMITS["chat_create"]["max_requests"] == 2
    assert scr.RATE_LIMITS["chat_create"]["window_seconds"] == 30
    assert scr.RATE_LIMIT_BACKOFF["base_seconds"] == 1
    assert scr.RATE_LIMIT_BACKOFF["max_seconds"] == 8

    # Keep global defaults stable for subsequent tests.
    scr.configure_rate_limits()


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


def test_rate_limited_responses_include_retry_after_header():
    _clear_store()
    client = _test_app.test_client()

    for _ in range(3):
        response = client.post("/chat/create", content_type="application/json")
        assert response.status_code == 200

    blocked = client.post("/chat/create", content_type="application/json")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    body = blocked.get_json()
    assert body is not None
    assert "retry_after" in body
    assert int(blocked.headers["Retry-After"]) == body["retry_after"]
