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
    assert "direct_messages" in data
    assert "message_mix" in data
    assert "room_activity" in data
    assert "rate_limits" in data
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


def test_chat_stats_message_mix_counts_encrypted_and_plaintext():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        room = ChatRoom("mix-room")
        room.add_message("u1", "PlainUser", [255, 85, 85], "hello plaintext")
        room.add_message("u2", "EncUser", [85, 170, 255], "ENC:YWJjMTIz")
        with rooms_lock:
            chat_rooms["mix-room"] = room

        data = client.get("/chat/stats").get_json()
        assert data["message_mix"]["plaintext_messages"] == 1
        assert data["message_mix"]["encrypted_messages"] == 1
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_dm_read_unread_breakdown():
    from simple_chat_routes import direct_messages, dm_lock

    client = _test_app.test_client()
    now = datetime.datetime.now()

    with dm_lock:
        saved = dict(direct_messages)
        direct_messages.clear()
        direct_messages["dm-unread"] = {
            "dm_id": "dm-unread",
            "sender_id": "u1",
            "sender_name": "Alice",
            "room_id": "room-a",
            "message": "join here",
            "timestamp": now,
            "read": False,
        }
        direct_messages["dm-read"] = {
            "dm_id": "dm-read",
            "sender_id": "u2",
            "sender_name": "Bob",
            "room_id": "room-b",
            "message": "seen message",
            "timestamp": now,
            "read": True,
        }

    try:
        data = client.get("/chat/stats").get_json()
        assert data["pending_dms"] == 2
        assert data["direct_messages"]["read"] == 1
        assert data["direct_messages"]["unread"] == 1
    finally:
        with dm_lock:
            direct_messages.clear()
            direct_messages.update(saved)


def test_chat_stats_room_activity_ages_present_when_data_exists():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()
    now = datetime.datetime.now()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        room = ChatRoom("activity-room")
        room.created_at = now - datetime.timedelta(seconds=120)
        room.add_message("u1", "Alice", [255, 85, 85], "older")
        room.add_message("u2", "Bob", [85, 170, 255], "newer")
        with room.lock:
            room.messages[0]["timestamp"] = now - datetime.timedelta(seconds=80)
            room.messages[1]["timestamp"] = now - datetime.timedelta(seconds=10)
        with rooms_lock:
            chat_rooms["activity-room"] = room

        data = client.get("/chat/stats").get_json()
        activity = data["room_activity"]
        assert activity["oldest_room_age_seconds"] >= activity["newest_room_age_seconds"] >= 0
        assert activity["oldest_message_age_seconds"] >= activity["newest_message_age_seconds"] >= 0
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_rate_limit_snapshot_includes_config_and_session_count():
    from simple_chat_routes import check_rate_limit, _rate_limit_lock, _rate_limit_store

    client = _test_app.test_client()
    with _rate_limit_lock:
        _rate_limit_store.clear()

    check_rate_limit("stats-session", "chat_create")
    data = client.get("/chat/stats").get_json()

    assert data["rate_limits"]["active_sessions"] >= 1
    configured = data["rate_limits"]["configured_endpoints"]
    assert configured["chat_create"]["max_requests"] == 10
    assert configured["chat_create"]["window_seconds"] == 60
    assert configured["chat_message"]["max_requests"] == 30
    assert configured["dm_send"]["max_requests"] == 5


def test_chat_stats_security_headers():
    """Stats endpoint should have the same security headers as other endpoints."""
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Server"] == ""
