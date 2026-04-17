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
