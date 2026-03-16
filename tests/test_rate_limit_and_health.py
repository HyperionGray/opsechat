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
    load_rate_limits_from_env,
    load_flask_rate_limits_from_env,
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


def test_load_rate_limits_from_env_overrides_defaults(monkeypatch):
    defaults = {"chat_create": {"max_requests": 10, "window_seconds": 60}}
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_CHAT_CREATE_MAX_REQUESTS", "7")
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_CHAT_CREATE_WINDOW_SECONDS", "120")

    config = load_rate_limits_from_env(defaults)

    assert config["chat_create"]["max_requests"] == 7
    assert config["chat_create"]["window_seconds"] == 120


def test_load_rate_limits_from_env_ignores_invalid_values(monkeypatch):
    defaults = {"dm_send": {"max_requests": 5, "window_seconds": 60}}
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_DM_SEND_MAX_REQUESTS", "-1")
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_DM_SEND_WINDOW_SECONDS", "abc")

    config = load_rate_limits_from_env(defaults)

    assert config["dm_send"]["max_requests"] == 5
    assert config["dm_send"]["window_seconds"] == 60


def test_load_flask_rate_limits_from_env_overrides_defaults(monkeypatch):
    defaults = {"chat_message": "60 per minute"}
    monkeypatch.setenv("OPSECHAT_FLASK_RATE_LIMIT_CHAT_MESSAGE", "45 per minute")

    config = load_flask_rate_limits_from_env(defaults)

    assert config["chat_message"] == "45 per minute"


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
