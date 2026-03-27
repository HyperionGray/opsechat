"""
Flask API endpoint integration tests for simple_chat_routes.

Covers: create room, post/get messages (including sanitization and base64
detection), automated key exchange endpoint, and ephemeral DM send/view.

Related GitHub issues: #109 (initial chat/email plan), #112 (release push),
#114 (simple web-app rooms), #116 (automated key exchange, DMs),
#118 (final functionality validation).
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_chat_routes import (
    chat_rooms,
    direct_messages,
    dm_lock,
    rooms_lock,
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
# /chat/create
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


# ===========================================================================
# /chat/room/<id>/messages
# ===========================================================================

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
        """XSS payload: angle brackets and script tags must be stripped."""
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "<script>alert('xss attempt')</script>"},
        )
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = resp.get_json()
        for msg in data["messages"]:
            assert "<script>" not in msg["message"]
            assert "</script>" not in msg["message"]
            assert "<" not in msg["message"]
            assert ">" not in msg["message"]

    def test_base64_like_payload_rejected(self):
        """Dense payloads with <5% spaces and length >100 must be rejected."""
        # Simulate a base64-encoded blob: long string, almost no spaces
        b64_like = "dGhpcyBpcyBhIHRlc3Q" * 6  # ~114 chars, no spaces
        resp = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": b64_like},
        )
        assert resp.status_code == 400

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


# ===========================================================================
# /chat/room/<id>/key  (automated key exchange)
# ===========================================================================

class TestRoomKeyEndpoint:
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


# ===========================================================================
# /chat/dm/send and /chat/dm/<id>
# ===========================================================================

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
        assert data["one_time_read"] is True

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

    def test_dm_is_not_available_after_first_read(self):
        resp = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "single use"},
        )
        dm_id = resp.get_json()["dm_id"]

        first = self.client.get(f"/chat/dm/{dm_id}")
        assert first.status_code == 200

        second = self.client.get(f"/chat/dm/{dm_id}")
        assert second.status_code == 404

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
        with dm_lock:
            assert "test-expired" not in direct_messages

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
