"""
Tests for rate limiting (simple_chat_routes) and the /health endpoint (app_factory).
"""

import datetime
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import check_rate_limit, _rate_limit_store, _rate_limit_lock

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
    assert "service" in data


def test_health_endpoint_active_rooms_is_integer():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["active_rooms"], int)
    assert data["active_rooms"] >= 0


def test_health_endpoint_returns_rate_limit_metadata():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    assert isinstance(data["rate_limited_sessions"], int)
    assert data["rate_limited_sessions"] >= 0
    assert isinstance(data["rate_limits"], dict)
    assert "chat_create" in data["rate_limits"]
    assert "chat_message" in data["rate_limits"]
    assert "dm_send" in data["rate_limits"]


def test_chat_create_rate_limit_returns_retry_after_header_and_metadata():
    _clear_store()
    client = _test_app.test_client()

    # chat_create allows 10 requests/minute; the 11th should be blocked
    for _ in range(10):
        response = client.post("/chat/create")
        assert response.status_code == 200

    blocked = client.post("/chat/create")
    assert blocked.status_code == 429

    data = blocked.get_json()
    assert data is not None
    assert data["code"] == "rate_limited"
    assert data["endpoint"] == "chat_create"
    assert data["limit"] == 10
    assert data["window_seconds"] == 60
    assert isinstance(data["retry_after"], int)
    assert data["retry_after"] >= 1
    assert blocked.headers.get("Retry-After") == str(data["retry_after"])
    assert blocked.headers.get("X-RateLimit-Limit") == "10"
    assert blocked.headers.get("X-RateLimit-Window") == "60"
    assert blocked.headers.get("X-RateLimit-Remaining") == "0"
