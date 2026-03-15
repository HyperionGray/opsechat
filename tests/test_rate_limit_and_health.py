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
    _load_rate_limits_from_env,
    DEFAULT_RATE_LIMITS,
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


def test_rate_limit_configuration_loads_from_environment(monkeypatch):
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", "2")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_WINDOW_SECONDS", "15")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS", "3")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS", "20")
    monkeypatch.setenv("OPSECHAT_DM_SEND_MAX_REQUESTS", "1")
    monkeypatch.setenv("OPSECHAT_DM_SEND_WINDOW_SECONDS", "10")

    configured = _load_rate_limits_from_env()

    assert configured["chat_create"] == {"max_requests": 2, "window_seconds": 15}
    assert configured["chat_message"] == {"max_requests": 3, "window_seconds": 20}
    assert configured["dm_send"] == {"max_requests": 1, "window_seconds": 10}


def test_rate_limit_configuration_invalid_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", "0")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS", "-9")
    monkeypatch.setenv("OPSECHAT_DM_SEND_MAX_REQUESTS", "invalid")

    configured = _load_rate_limits_from_env()

    assert configured["chat_create"] == DEFAULT_RATE_LIMITS["chat_create"]
    assert configured["chat_message"] == DEFAULT_RATE_LIMITS["chat_message"]
    assert configured["dm_send"] == DEFAULT_RATE_LIMITS["dm_send"]


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


def test_health_endpoint_includes_rate_limit_metadata():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    assert "rate_limits" in data
    assert data["rate_limits"]["chat_message"]["max_requests"] >= 1
    assert "email_send_rate_limit" in data
    assert data["email_send_rate_limit"]["max_sends_per_window"] >= 1
