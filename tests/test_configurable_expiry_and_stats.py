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


def test_chat_stats_include_rooms_default_off():
    client = _test_app.test_client()
    data = client.get("/chat/stats").get_json()
    assert "rooms" not in data
    assert "rooms_returned" not in data
    assert "rooms_truncated" not in data


def test_chat_stats_include_rooms_returns_room_diagnostics():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        older = ChatRoom("older-room")
        newer = ChatRoom("newer-room")

        older.add_message("u1", "OldUser", [255, 85, 85], "first")
        newer.add_message("u2", "NewUser", [85, 170, 255], "second")

        # Ensure deterministic order for "most recently active first"
        with older.lock:
            older.messages[-1]["timestamp"] = datetime.datetime.now() - datetime.timedelta(seconds=30)
        with newer.lock:
            newer.messages[-1]["timestamp"] = datetime.datetime.now()

        with rooms_lock:
            chat_rooms["older-room"] = older
            chat_rooms["newer-room"] = newer

        data = client.get("/chat/stats?include_rooms=1").get_json()

        assert "rooms" in data
        assert data["rooms_returned"] == 2
        assert data["rooms_truncated"] is False
        assert isinstance(data["rooms"], list)
        assert data["rooms"][0]["room_id"] == "newer-room"

        sample = data["rooms"][0]
        assert "message_count" in sample
        assert "active_users" in sample
        assert "created_at" in sample
        assert "last_activity_at" in sample
        assert "room_age_seconds" in sample
        assert "seconds_since_last_activity" in sample
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_include_rooms_respects_room_limit():
    from simple_chat_routes import chat_rooms, rooms_lock, ChatRoom

    client = _test_app.test_client()

    with rooms_lock:
        saved = dict(chat_rooms)
        chat_rooms.clear()

    try:
        with rooms_lock:
            for idx in range(3):
                room = ChatRoom(f"room-{idx}")
                room.add_message(f"u{idx}", f"User{idx}", [255, 85, 85], f"msg-{idx}")
                chat_rooms[f"room-{idx}"] = room

        data = client.get("/chat/stats?include_rooms=true&room_limit=2").get_json()
        assert data["rooms_returned"] == 2
        assert data["rooms_truncated"] is True
        assert len(data["rooms"]) == 2
    finally:
        with rooms_lock:
            chat_rooms.clear()
            chat_rooms.update(saved)


def test_chat_stats_invalid_room_limit_returns_400():
    client = _test_app.test_client()

    bad_values = ["0", "201", "abc"]
    for value in bad_values:
        resp = client.get(f"/chat/stats?include_rooms=1&room_limit={value}")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


def test_chat_stats_security_headers():
    """Stats endpoint should have the same security headers as other endpoints."""
    client = _test_app.test_client()
    resp = client.get("/chat/stats")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Server"] == ""
