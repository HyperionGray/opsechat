"""
Unit and integration tests for Simple Chat features (v0.8.0).

Covers the features recently pushed in issues #109, #112, #114, #116, #118:
  - Cryptographically secure room / DM ID generation
  - ChatRoom class (message lifecycle, auto-expiry, memory overwriting)
  - Automated key exchange (room encryption key)
  - Direct message (DM) system (send, view, expiry, cleanup)
  - Random username and color generation
  - Room cleanup (inactive > 1 hour)
  - Flask API endpoints (create room, post/get messages, key endpoint, DM send/view)
  - Security headers (CSP, X-Frame-Options, etc.)
  - Message sanitization (XSS, length limits, base64 detection)
  - Per-session rate limiting is tested separately in test_rate_limit_and_health.py
"""

import datetime
import os
import sys

import pytest

# Ensure the project root is on sys.path so imports work in all environments.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_chat_routes import (
    ChatRoom,
    cleanup_old_dms,
    cleanup_old_rooms,
    direct_messages,
    dm_lock,
    chat_rooms,
    rooms_lock,
    generate_random_username,
    generate_secure_dm_id,
    generate_secure_room_id,
    get_random_color_rgb,
    MAX_MESSAGE_LENGTH,
)
from app_factory import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_app():
    """Return a configured test Flask application."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


def _clear_rooms():
    with rooms_lock:
        chat_rooms.clear()


def _clear_dms():
    with dm_lock:
        direct_messages.clear()


# ===========================================================================
# Secure ID generation
# ===========================================================================

class TestSecureIdGeneration:
    def test_room_ids_are_unique(self):
        ids = {generate_secure_room_id() for _ in range(50)}
        assert len(ids) == 50

    def test_room_id_minimum_length(self):
        # secrets.token_urlsafe(32) produces at least 43 chars
        for _ in range(10):
            rid = generate_secure_room_id()
            assert len(rid) >= 40, f"Room ID too short: {rid!r}"

    def test_dm_ids_are_unique(self):
        ids = {generate_secure_dm_id() for _ in range(50)}
        assert len(ids) == 50

    def test_dm_id_minimum_length(self):
        for _ in range(10):
            did = generate_secure_dm_id()
            assert len(did) >= 16, f"DM ID too short: {did!r}"

    def test_room_id_url_safe(self):
        """Room ID must be safe to embed in a URL path segment."""
        rid = generate_secure_room_id()
        invalid = set(" /\\?#%")
        assert not (set(rid) & invalid), f"Room ID contains unsafe chars: {rid!r}"


# ===========================================================================
# Username and color generation
# ===========================================================================

class TestUsernameColorGeneration:
    def test_username_pattern(self):
        """Username must match Adjective+Noun+4digit format."""
        import re
        pattern = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+\d{4}$")
        for _ in range(20):
            name = generate_random_username()
            assert pattern.match(name), f"Username does not match pattern: {name!r}"

    def test_usernames_are_varied(self):
        names = {generate_random_username() for _ in range(30)}
        # Very unlikely to get all the same with 12*12*9999 combinations
        assert len(names) > 1

    def test_color_is_list_of_three_ints(self):
        color = get_random_color_rgb()
        assert isinstance(color, list)
        assert len(color) == 3
        for channel in color:
            assert isinstance(channel, int)
            assert 0 <= channel <= 255

    def test_colors_are_varied(self):
        colors = {tuple(get_random_color_rgb()) for _ in range(50)}
        # Palette has 10 entries; with 50 draws we must hit more than 1
        assert len(colors) > 1


# ===========================================================================
# ChatRoom class
# ===========================================================================

class TestChatRoom:
    def test_room_has_encryption_key_on_creation(self):
        room = ChatRoom("test-room-key")
        key = room.get_room_key()
        assert key, "Room key must not be empty"
        # Base64-encoded 32 bytes → 44 chars
        assert len(key) >= 40

    def test_each_room_has_unique_key(self):
        keys = {ChatRoom(f"r{i}").get_room_key() for i in range(20)}
        assert len(keys) == 20

    def test_add_and_retrieve_message(self):
        room = ChatRoom("msg-test")
        room.add_message("u1", "SwiftRaven0001", [255, 85, 85], "hello world")
        messages = room.get_messages()
        assert len(messages) == 1
        assert messages[0]["message"] == "hello world"
        assert messages[0]["username"] == "SwiftRaven0001"

    def test_get_messages_returns_copy(self):
        room = ChatRoom("copy-test")
        room.add_message("u1", "name", [1, 2, 3], "msg")
        msgs1 = room.get_messages()
        msgs1.clear()
        msgs2 = room.get_messages()
        assert len(msgs2) == 1

    def test_messages_expire_after_three_minutes(self):
        room = ChatRoom("expiry-test")
        room.add_message("u1", "name", [1, 2, 3], "old message")
        # Back-date the message timestamp to 4 minutes ago
        with room.lock:
            room.messages[0]["timestamp"] = (
                datetime.datetime.now() - datetime.timedelta(minutes=4)
            )
        messages = room.get_messages()
        assert len(messages) == 0, "Expired message should be removed"

    def test_expired_message_data_is_overwritten(self):
        room = ChatRoom("overwrite-test")
        room.add_message("u1", "VoidTiger0042", [1, 2, 3], "secret content")
        with room.lock:
            msg = room.messages[0]
            msg["timestamp"] = (
                datetime.datetime.now() - datetime.timedelta(minutes=5)
            )
        room.cleanup_old_messages()
        # The message dict still exists in local variable; confirm fields wiped
        assert msg["message"] == "X" * len("secret content")
        assert msg["username"] == "X" * len("VoidTiger0042")

    def test_recent_messages_are_not_expired(self):
        room = ChatRoom("keep-test")
        room.add_message("u1", "n", [1, 2, 3], "fresh")
        messages = room.get_messages()
        assert len(messages) == 1

    def test_user_count_increments(self):
        room = ChatRoom("count-test")
        assert room.get_user_count() == 0
        room.add_message("u1", "Alice1", [1, 2, 3], "hi")
        assert room.get_user_count() == 1
        room.add_message("u2", "Bob2", [4, 5, 6], "hey")
        assert room.get_user_count() == 2

    def test_user_count_excludes_stale_users(self):
        room = ChatRoom("stale-count-test")
        room.add_message("u1", "OldUser", [1, 2, 3], "ancient msg")
        # Back-date user's last_seen to beyond 5-minute activity window
        with room.lock:
            room.users["u1"]["last_seen"] = (
                datetime.datetime.now() - datetime.timedelta(minutes=10)
            )
        assert room.get_user_count() == 0


# ===========================================================================
# Room cleanup
# ===========================================================================

class TestRoomCleanup:
    def setup_method(self):
        _clear_rooms()

    def test_active_room_is_not_deleted(self):
        with rooms_lock:
            chat_rooms["active-room"] = ChatRoom("active-room")
        cleanup_old_rooms()
        with rooms_lock:
            assert "active-room" in chat_rooms

    def test_inactive_room_is_deleted_after_one_hour(self):
        room = ChatRoom("old-room")
        # Back-date creation time
        room.created_at = datetime.datetime.now() - datetime.timedelta(hours=2)
        with rooms_lock:
            chat_rooms["old-room"] = room
        cleanup_old_rooms()
        with rooms_lock:
            assert "old-room" not in chat_rooms

    def test_room_with_old_last_message_is_deleted(self):
        room = ChatRoom("stale-msg-room")
        room.add_message("u1", "name", [1, 2, 3], "old")
        with room.lock:
            room.messages[0]["timestamp"] = (
                datetime.datetime.now() - datetime.timedelta(hours=2)
            )
        with rooms_lock:
            chat_rooms["stale-msg-room"] = room
        cleanup_old_rooms()
        with rooms_lock:
            assert "stale-msg-room" not in chat_rooms


# ===========================================================================
# Direct message system
# ===========================================================================

class TestDirectMessages:
    def setup_method(self):
        _clear_dms()

    def test_expired_dms_are_removed(self):
        with dm_lock:
            direct_messages["expired-dm"] = {
                "dm_id": "expired-dm",
                "sender_id": "u1",
                "sender_name": "Alice",
                "room_id": "some-room",
                "message": "here is the room link",
                "timestamp": datetime.datetime.now() - datetime.timedelta(seconds=90),
                "read": False,
            }
        cleanup_old_dms()
        with dm_lock:
            assert "expired-dm" not in direct_messages

    def test_fresh_dm_is_not_removed(self):
        with dm_lock:
            direct_messages["fresh-dm"] = {
                "dm_id": "fresh-dm",
                "sender_id": "u1",
                "sender_name": "Alice",
                "room_id": "some-room",
                "message": "here is the room link",
                "timestamp": datetime.datetime.now(),
                "read": False,
            }
        cleanup_old_dms()
        with dm_lock:
            assert "fresh-dm" in direct_messages

    def test_expired_dm_message_data_is_overwritten(self):
        original_message = "secret room invite"
        original_room_id = "super-secret-room-id"
        dm = {
            "dm_id": "overwrite-dm",
            "sender_id": "u1",
            "sender_name": "Alice",
            "room_id": original_room_id,
            "message": original_message,
            "timestamp": datetime.datetime.now() - datetime.timedelta(seconds=90),
            "read": False,
        }
        with dm_lock:
            direct_messages["overwrite-dm"] = dm
        cleanup_old_dms()
        assert dm["message"] == "X" * len(original_message)
        assert dm["room_id"] == "X" * len(original_room_id)


# ===========================================================================
# Flask API endpoint integration tests
# ===========================================================================

class TestChatCreateEndpoint:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def test_create_room_returns_success(self):
        resp = self.client.post("/chat/create")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_create_room_returns_room_id(self):
        resp = self.client.post("/chat/create")
        data = resp.get_json()
        assert "room_id" in data
        assert len(data["room_id"]) >= 40

    def test_create_room_returns_room_url(self):
        resp = self.client.post("/chat/create")
        data = resp.get_json()
        assert "room_url" in data
        assert data["room_url"].startswith("/chat/room/")

    def test_created_room_is_accessible(self):
        create_resp = self.client.post("/chat/create")
        room_id = create_resp.get_json()["room_id"]
        room_resp = self.client.get(f"/chat/room/{room_id}")
        assert room_resp.status_code == 200

    def test_unknown_room_returns_404(self):
        resp = self.client.get("/chat/room/nonexistent-room-id-12345678")
        assert resp.status_code == 404


class TestChatMessagesEndpoint:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()
        # Create a room for each test
        resp = self.client.post("/chat/create")
        self.room_id = resp.get_json()["room_id"]

    def test_get_messages_returns_empty_list_initially(self):
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"] == []

    def test_post_message_success(self):
        resp = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "hello test"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_posted_message_appears_in_get(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "visible message"},
        )
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = resp.get_json()
        messages = [m["message"] for m in data["messages"]]
        assert "visible message" in messages

    def test_get_messages_returns_user_count(self):
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = resp.get_json()
        assert "user_count" in data
        assert isinstance(data["user_count"], int)

    def test_empty_message_rejected(self):
        resp = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "   "},
        )
        assert resp.status_code == 400

    def test_missing_message_field_rejected(self):
        resp = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"other_field": "value"},
        )
        assert resp.status_code == 400

    def test_message_over_max_length_rejected(self):
        long_msg = "a " * (MAX_MESSAGE_LENGTH + 10)
        resp = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": long_msg},
        )
        assert resp.status_code == 400

    def test_html_tags_stripped_from_message(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "safe text"},
        )
        # Directly inject an XSS payload through the route, including actual <script> tags
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "<script>alert('xss attempt')</script>"},
        )
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = resp.get_json()
        for msg in data["messages"]:
            assert "<script>" not in msg["message"]
            assert "</script>" not in msg["message"]

    def test_get_on_missing_room_returns_404(self):
        resp = self.client.get("/chat/room/no-such-room-xyz/messages")
        assert resp.status_code == 404

    def test_message_response_contains_expected_fields(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "field check"},
        )
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = resp.get_json()
        msg = data["messages"][0]
        for field in ("username", "color", "message", "timestamp", "is_mine"):
            assert field in msg, f"Missing field: {field}"


class TestRoomKeyEndpoint:
    """Automated key exchange: each room exposes a /key endpoint."""

    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def test_key_endpoint_returns_key(self):
        resp = self.client.post("/chat/create")
        room_id = resp.get_json()["room_id"]
        key_resp = self.client.get(f"/chat/room/{room_id}/key")
        assert key_resp.status_code == 200
        data = key_resp.get_json()
        assert "encryption_key" in data
        assert len(data["encryption_key"]) >= 40

    def test_key_is_consistent_for_same_room(self):
        resp = self.client.post("/chat/create")
        room_id = resp.get_json()["room_id"]
        key1 = self.client.get(f"/chat/room/{room_id}/key").get_json()["encryption_key"]
        key2 = self.client.get(f"/chat/room/{room_id}/key").get_json()["encryption_key"]
        assert key1 == key2

    def test_different_rooms_have_different_keys(self):
        resp1 = self.client.post("/chat/create")
        resp2 = self.client.post("/chat/create")
        key1 = self.client.get(
            f"/chat/room/{resp1.get_json()['room_id']}/key"
        ).get_json()["encryption_key"]
        key2 = self.client.get(
            f"/chat/room/{resp2.get_json()['room_id']}/key"
        ).get_json()["encryption_key"]
        assert key1 != key2

    def test_key_endpoint_on_missing_room_returns_404(self):
        resp = self.client.get("/chat/room/no-room-here/key")
        assert resp.status_code == 404


class TestDMEndpoints:
    """API-level tests for the ephemeral DM system."""

    def setup_method(self):
        _clear_rooms()
        _clear_dms()
        self.app = _fresh_app()
        self.client = self.app.test_client()
        # Create a room to reference in DMs
        resp = self.client.post("/chat/create")
        self.room_id = resp.get_json()["room_id"]

    def test_send_dm_success(self):
        resp = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "join my room"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "dm_id" in data
        assert data["expires_in"] == 60

    def test_send_dm_creates_viewable_link(self):
        resp = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "join my room"},
        )
        dm_id = resp.get_json()["dm_id"]
        view_resp = self.client.get(f"/chat/dm/{dm_id}")
        assert view_resp.status_code == 200
        data = view_resp.get_json()
        assert "message" in data
        assert "room_id" in data

    def test_dm_has_expiry_field(self):
        resp = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "test"},
        )
        dm_id = resp.get_json()["dm_id"]
        view_resp = self.client.get(f"/chat/dm/{dm_id}")
        data = view_resp.get_json()
        assert "expires_in" in data
        assert data["expires_in"] <= 60

    def test_expired_dm_returns_404(self):
        """Manually insert an expired DM and verify the endpoint rejects it."""
        with dm_lock:
            direct_messages["test-expired"] = {
                "dm_id": "test-expired",
                "sender_id": "u1",
                "sender_name": "Alice",
                "room_id": self.room_id,
                "message": "old invite",
                "timestamp": datetime.datetime.now() - datetime.timedelta(seconds=90),
                "read": False,
            }
        view_resp = self.client.get("/chat/dm/test-expired")
        assert view_resp.status_code == 404

    def test_nonexistent_dm_returns_404(self):
        resp = self.client.get("/chat/dm/does-not-exist-at-all")
        assert resp.status_code == 404

    def test_send_dm_missing_fields_rejected(self):
        resp = self.client.post("/chat/dm/send", json={"room_id": self.room_id})
        assert resp.status_code == 400

    def test_send_dm_too_long_rejected(self):
        resp = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "x" * 201},
        )
        assert resp.status_code == 400


# ===========================================================================
# Security headers
# ===========================================================================

class TestSecurityHeaders:
    def setup_method(self):
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def _headers(self, path="/"):
        return self.client.get(path).headers

    def test_csp_header_present(self):
        h = self._headers()
        assert "Content-Security-Policy" in h

    def test_csp_disallows_inline_scripts(self):
        csp = self._headers()["Content-Security-Policy"]
        # Must not contain 'unsafe-inline' for scripts
        assert "unsafe-inline" not in csp

    def test_x_content_type_options(self):
        h = self._headers()
        assert h.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_deny(self):
        h = self._headers()
        assert h.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_no_referrer(self):
        h = self._headers()
        assert h.get("Referrer-Policy") == "no-referrer"

    def test_server_header_stripped(self):
        h = self._headers()
        assert h.get("Server", "") == ""
