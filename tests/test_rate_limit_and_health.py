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
    calculate_exponential_backoff,
    RATE_LIMITS,
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


def _seed_exhausted_session_limit(session_id, endpoint):
    """Populate in-memory store so the next call is definitely rate-limited."""
    cfg = RATE_LIMITS[endpoint]
    with _rate_limit_lock:
        _rate_limit_store.setdefault(session_id, {})
        _rate_limit_store[session_id][endpoint] = [
            datetime.datetime.now() - datetime.timedelta(seconds=1)
            for _ in range(cfg["max_requests"])
        ]


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


def test_exponential_backoff_calculation_and_cap():
    assert calculate_exponential_backoff(2, attempt=0, cap_seconds=30) == 2
    assert calculate_exponential_backoff(2, attempt=1, cap_seconds=30) == 4
    assert calculate_exponential_backoff(2, attempt=2, cap_seconds=30) == 8
    assert calculate_exponential_backoff(2, attempt=10, cap_seconds=30) == 30


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


def test_dm_rate_limit_response_contains_retry_headers_and_payload():
    _clear_store()
    client = _test_app.test_client()
    sid = "session-dm-429"

    with client.session_transaction() as sess:
        sess["_id"] = sid
        sess["username"] = "TestUser"
        sess["color"] = [1, 2, 3]

    _seed_exhausted_session_limit(sid, "dm_send")
    response = client.post(
        "/chat/dm/send",
        json={"room_id": "room-abc", "message": "hello"},
    )

    assert response.status_code == 429
    data = response.get_json()
    assert data is not None
    assert "error" in data
    assert data["retry_after"] >= 1
    assert data["backoff_seconds"] >= data["retry_after"]
    assert response.headers.get("Retry-After") == str(data["retry_after"])
    assert response.headers.get("X-Backoff-Seconds") == str(data["backoff_seconds"])
