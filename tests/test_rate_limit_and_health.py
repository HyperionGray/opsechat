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
    RATE_LIMITS,
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


def test_rate_limit_backoff_increases_after_repeated_violations():
    _clear_store()
    sid = "session-backoff"
    endpoint = "dm_send"
    limit = RATE_LIMITS[endpoint]["max_requests"]

    # Seed store at limit to force an immediate violation.
    with _rate_limit_lock:
        _rate_limit_store[sid] = {
            endpoint: [datetime.datetime.now()] * limit
        }
        _rate_limit_backoff_store[sid] = {
            endpoint: {
                "violations": 0,
                "blocked_until": None,
                "last_violation": None,
            }
        }

    allowed, first_retry_after = check_rate_limit(sid, endpoint)
    assert allowed is False
    assert first_retry_after >= 1

    # Simulate cooldown expiry while still at window limit to trigger
    # a second violation and stronger penalty.
    with _rate_limit_lock:
        _rate_limit_backoff_store[sid][endpoint]["blocked_until"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=1)
        )

    allowed, second_retry_after = check_rate_limit(sid, endpoint)
    assert allowed is False
    assert second_retry_after >= first_retry_after

    with _rate_limit_lock:
        assert _rate_limit_backoff_store[sid][endpoint]["violations"] >= 2


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


def test_chat_message_rate_limit_includes_retry_metadata():
    _clear_store()
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    client = app.test_client()

    create_resp = client.post("/chat/create", content_type="application/json")
    assert create_resp.status_code == 200
    room_id = create_resp.get_json()["room_id"]

    # chat_message limit: 30 per minute
    for i in range(30):
        msg_resp = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": f"message-{i}"},
        )
        assert msg_resp.status_code == 200

    blocked_resp = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": "blocked-message"},
    )
    assert blocked_resp.status_code == 429
    payload = blocked_resp.get_json()
    assert payload["retry_strategy"] == "exponential_backoff"
    assert isinstance(payload["retry_after"], int)
    assert payload["retry_after"] >= 1
    assert blocked_resp.headers.get("Retry-After") == str(payload["retry_after"])
    assert (
        blocked_resp.headers.get("X-RateLimit-Retry-After")
        == str(payload["retry_after"])
    )
