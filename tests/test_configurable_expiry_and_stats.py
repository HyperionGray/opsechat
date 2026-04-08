"""
Tests for configurable expiry settings, dynamic health room count, and /chat/stats endpoint.

Covers:
- Environment-variable-driven expiry constants
- Health endpoint reporting actual room count
- /chat/stats endpoint returning operational metrics
"""

import datetime
import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app

_test_app = create_app()


# ---------------------------------------------------------------------------
# Configurable expiry defaults (no env override in test environment)
# ---------------------------------------------------------------------------

def test_default_message_expiry():
    from simple_chat_routes import MESSAGE_EXPIRY_SECONDS
    assert MESSAGE_EXPIRY_SECONDS == 180  # 3 minutes default


def test_default_dm_expiry():
    from simple_chat_routes import DM_EXPIRY_SECONDS
    assert DM_EXPIRY_SECONDS == 60  # 1 minute default


def test_default_room_inactive():
    from simple_chat_routes import ROOM_INACTIVE_SECONDS
    assert ROOM_INACTIVE_SECONDS == 3600  # 1 hour default


# ---------------------------------------------------------------------------
# Health endpoint room count (dynamic)
# ---------------------------------------------------------------------------

def test_health_active_rooms_reflects_chat_rooms():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    # Baseline: no rooms
    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        resp = client.get("/health")
        data = resp.get_json()
        assert data["active_rooms"] == 0

        # Add two rooms
        with rooms_lock:
            chat_rooms["room-a"] = ChatRoom("room-a")
            chat_rooms["room-b"] = ChatRoom("room-b")

        resp = client.get("/health")
        data = resp.get_json()
        assert data["active_rooms"] == 2
    finally:
        # Restore original state
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


# ---------------------------------------------------------------------------
# /chat/stats endpoint
# ---------------------------------------------------------------------------

def test_chat_stats_returns_200():
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    assert resp.status_code == 200


def test_chat_stats_required_fields():
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    data = resp.get_json()
    assert "active_rooms" in data
    assert "total_messages" in data
    assert "active_users" in data
    assert "pending_dms" in data
    assert "config" in data


def test_chat_stats_config_includes_expiry_settings():
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    data = resp.get_json()
    config = data["config"]
    assert config["message_expiry_seconds"] == 180
    assert config["dm_expiry_seconds"] == 60
    assert config["room_inactive_seconds"] == 3600


def test_chat_stats_counts_rooms_and_messages():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        # Empty state
        data = client.get("/chat/stats").get_json()
        assert data["active_rooms"] == 0
        assert data["total_messages"] == 0

        # Add a room with a message
        room = ChatRoom("stats-room")
        room.add_message("u1", "TestUser", [255, 85, 85], "hello")
        with rooms_lock:
            chat_rooms["stats-room"] = room

        data = client.get("/chat/stats").get_json()
        assert data["active_rooms"] == 1
        assert data["total_messages"] == 1
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_security_headers():
    """Stats endpoint should have the same security headers as other endpoints."""
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Server"] == ""


def test_chat_stats_excludes_optional_sections_by_default():
    client = _test_app.test_client()
    data = client.get("/chat/stats").get_json()
    assert "rooms" not in data
    assert "rate_limits" not in data
    assert data["snapshot"]["refreshed"] is False


def test_chat_stats_include_rooms_query_flag():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        room = ChatRoom("telemetry-room")
        room.add_message("u1", "Alpha", [255, 85, 85], "hello")
        with rooms_lock:
            chat_rooms["telemetry-room"] = room

        data = client.get("/chat/stats?include_rooms=1").get_json()
        assert "rooms" in data
        assert len(data["rooms"]) == 1
        detail = data["rooms"][0]
        assert detail["room_id"] == "telemetry-room"
        assert detail["message_count"] == 1
        assert detail["active_users"] >= 1
        assert detail["created_at"] is not None
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_include_rate_limits_query_flag():
    from simple_chat_routes import check_rate_limit, _rate_limit_store, _rate_limit_lock

    client = _test_app.test_client()
    with _rate_limit_lock:
        _rate_limit_store.clear()

    # Populate in-memory windows for two endpoints.
    check_rate_limit("stats-session", "dm_send")
    check_rate_limit("stats-session", "chat_message")

    data = client.get("/chat/stats?include_rate_limits=true").get_json()
    assert "rate_limits" in data
    assert data["rate_limits"]["active_sessions"] >= 1
    assert "dm_send" in data["rate_limits"]["by_endpoint"]
    assert "chat_message" in data["rate_limits"]["by_endpoint"]
    assert data["rate_limits"]["by_endpoint"]["dm_send"]["tracked_requests"] >= 1
    assert data["rate_limits"]["by_endpoint"]["chat_message"]["tracked_requests"] >= 1


def test_chat_stats_refresh_flag_cleans_expired_data():
    from simple_chat_routes import (
        chat_rooms, rooms_lock, ChatRoom, MESSAGE_EXPIRY_SECONDS,
        direct_messages, dm_lock, DM_EXPIRY_SECONDS,
    )

    client = _test_app.test_client()

    with rooms_lock:
        saved_rooms = dict(chat_rooms)
        chat_rooms.clear()
    with dm_lock:
        saved_dms = dict(direct_messages)
        direct_messages.clear()

    try:
        # Add room with expired message; refresh should clear old message.
        room = ChatRoom("cleanup-room")
        room.add_message("u1", "Cleaner", [255, 85, 85], "old message")
        with room.lock:
            room.messages[0]["timestamp"] = datetime.datetime.now() - datetime.timedelta(
                seconds=MESSAGE_EXPIRY_SECONDS + 1
            )
        with rooms_lock:
            chat_rooms["cleanup-room"] = room

        # Add expired DM; refresh should remove it.
        with dm_lock:
            direct_messages["expired-dm"] = {
                "dm_id": "expired-dm",
                "sender_id": "u1",
                "sender_name": "Cleaner",
                "room_id": "cleanup-room",
                "message": "stale",
                "timestamp": datetime.datetime.now() - datetime.timedelta(
                    seconds=DM_EXPIRY_SECONDS + 1
                ),
                "read": False,
            }

        before = client.get("/chat/stats").get_json()
        assert before["total_messages"] == 1
        assert before["pending_dms"] == 1

        after = client.get("/chat/stats?refresh=on").get_json()
        assert after["snapshot"]["refreshed"] is True
        assert after["total_messages"] == 0
        assert after["pending_dms"] == 0
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved_rooms)
        with dm_lock:
            direct_messages.clear()
            direct_messages.update(saved_dms)
