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


def test_rate_limit_cooldown_blocks_even_if_request_window_is_cleared():
    _clear_store()
    sid = "session-cooldown"

    # Trigger first violation on dm_send (5/min)
    for _ in range(5):
        allowed, _ = check_rate_limit(sid, "dm_send")
        assert allowed is True
    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after >= 5

    # Simulate cleared request history while cooldown is still active
    with _rate_limit_lock:
        _rate_limit_store[sid]["dm_send"] = []

    # Should still be blocked due to cooldown
    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_backoff_escalates_on_repeated_violations():
    _clear_store()
    sid = "session-backoff"
    now = datetime.datetime.now()

    # Force first violation
    with _rate_limit_lock:
        _rate_limit_store[sid] = {"dm_send": [now] * 5}
    allowed, retry_after_first = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after_first >= 5

    # Expire cooldown only (keep violation history) and trigger violation again.
    with _rate_limit_lock:
        _rate_limit_backoff_store[sid]["dm_send"]["cooldown_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )
        _rate_limit_store[sid]["dm_send"] = [datetime.datetime.now()] * 5

    allowed, retry_after_second = check_rate_limit(sid, "dm_send")
    assert allowed is False
    assert retry_after_second >= 10


def test_chat_message_rate_limited_response_includes_retry_metadata():
    _clear_store()
    client = _test_app.test_client()
    create_response = client.post("/chat/create", json={})
    assert create_response.status_code == 200
    room_id = create_response.get_json()["room_id"]

    for i in range(30):
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": f"hello-{i}"},
        )
        assert response.status_code == 200

    response = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": "blocked"},
    )
    assert response.status_code == 429
    data = response.get_json()
    assert data is not None
    assert data.get("rate_limited") is True
    assert isinstance(data.get("retry_after"), int)
    assert data["retry_after"] >= 1
    assert response.headers.get("Retry-After") == str(data["retry_after"])


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
