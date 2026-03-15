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


def test_health_endpoint_active_rooms_is_integer():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["active_rooms"], int)
    assert data["active_rooms"] >= 0


def test_health_details_endpoint_returns_runtime_fields():
    _clear_store()
    client = _test_app.test_client()
    response = client.get("/health/details")
    assert response.status_code == 200

    data = response.get_json()
    assert data is not None
    assert data.get("status") == "healthy"
    assert data.get("service") == "opsechat"
    assert isinstance(data.get("uptime_seconds"), int)
    assert data["uptime_seconds"] >= 0

    runtime = data.get("runtime")
    assert isinstance(runtime, dict)
    assert isinstance(runtime.get("active_rooms"), int)
    assert isinstance(runtime.get("active_direct_messages"), int)
    assert isinstance(runtime.get("rate_limiter_sessions"), int)
    assert isinstance(runtime.get("rate_limits"), dict)
    assert "chat_message" in runtime["rate_limits"]


def test_chat_rate_limit_status_endpoint_returns_all_limits():
    _clear_store()
    client = _test_app.test_client()
    response = client.get("/chat/rate-limit-status")
    assert response.status_code == 200

    data = response.get_json()
    assert data is not None
    assert "limits" in data
    assert set(data["limits"].keys()) == {"chat_create", "chat_message", "dm_send"}


def test_chat_rate_limit_status_reflects_current_usage():
    _clear_store()
    client = _test_app.test_client()

    with client.session_transaction() as sess:
        sess["_id"] = "session-status"
        sess["username"] = "TestUser"
        sess["color"] = [255, 85, 85]

    # Consume two dm_send requests for this session
    check_rate_limit("session-status", "dm_send")
    check_rate_limit("session-status", "dm_send")

    response = client.get("/chat/rate-limit-status")
    assert response.status_code == 200
    data = response.get_json()

    dm_send = data["limits"]["dm_send"]
    assert dm_send["used_requests"] == 2
    assert dm_send["remaining_requests"] == 3
    assert dm_send["max_requests"] == 5
    assert dm_send["window_seconds"] == 60
