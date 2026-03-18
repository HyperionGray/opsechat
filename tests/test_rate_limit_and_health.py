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


# ---------------------------------------------------------------------------
# Rate-limit API response integration tests
# ---------------------------------------------------------------------------

def test_rate_limit_status_endpoint_reports_expected_shape():
    _clear_store()
    client = _test_app.test_client()

    response = client.get("/chat/rate-limit-status")
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()

    assert "limits" in data
    assert "timestamp" in data

    limits = data["limits"]
    for endpoint, config in RATE_LIMITS.items():
        assert endpoint in limits
        assert limits[endpoint]["max_requests"] == config["max_requests"]
        assert limits[endpoint]["window_seconds"] == config["window_seconds"]
        assert limits[endpoint]["used"] == 0
        assert limits[endpoint]["retry_after_seconds"] == 0


def test_rate_limit_status_updates_after_requests():
    _clear_store()
    client = _test_app.test_client()

    # Consume part of chat_create quota (3/min)
    for _ in range(2):
        r = client.post("/chat/create", content_type="application/json")
        assert r.status_code == 200

    status = client.get("/chat/rate-limit-status")
    data = status.get_json()
    chat_create = data["limits"]["chat_create"]

    assert chat_create["used"] == 2
    assert chat_create["remaining"] == 1
    assert chat_create["retry_after_seconds"] == 0


def test_dm_rate_limit_returns_retry_metadata():
    _clear_store()
    client = _test_app.test_client()

    payload = {"room_id": "room-123", "message": "hello"}
    for _ in range(5):
        r = client.post("/chat/dm/send", json=payload)
        assert r.status_code == 200

    blocked = client.post("/chat/dm/send", json=payload)
    assert blocked.status_code == 429
    assert blocked.is_json

    data = blocked.get_json()
    assert data["error"] == "rate_limit_exceeded"
    assert data["endpoint"] == "dm_send"
    assert data["retry_after_seconds"] >= 1
    assert data["limit"]["max_requests"] == 5
    assert data["limit"]["window_seconds"] == 60
    assert data["backoff"]["strategy"] == "exponential"
    assert data["backoff"]["schedule_seconds"][0] == data["retry_after_seconds"]

    retry_after_header = blocked.headers.get("Retry-After")
    assert retry_after_header is not None
    assert int(retry_after_header) == data["retry_after_seconds"]
