"""
Tests for incremental simple chat message sync metadata and since filtering.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import simple_chat_routes
from app_factory import create_app
from rate_limiter import limiter


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-simple-chat-sync"
    return app


def _clear_rooms():
    with simple_chat_routes.rooms_lock:
        simple_chat_routes.chat_rooms.clear()


def _clear_rate_limits(app):
    with simple_chat_routes._rate_limit_lock:
        simple_chat_routes._rate_limit_store.clear()
    with app.app_context():
        limiter.reset()


class TestSimpleChatIncrementalSync:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        _clear_rate_limits(self.app)
        self.client = self.app.test_client()
        self.room_id = simple_chat_routes.generate_secure_room_id(16)
        with simple_chat_routes.rooms_lock:
            simple_chat_routes.chat_rooms[self.room_id] = simple_chat_routes.ChatRoom(self.room_id)

    def test_messages_include_seq_and_sync_metadata(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "first"},
        )
        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"]
        assert isinstance(data["messages"][0]["seq"], int)
        assert isinstance(data["latest_seq"], int)
        assert isinstance(data["pruned_through_seq"], int)

    def test_since_only_returns_newer_messages(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "m1"},
        )
        first = self.client.get(f"/chat/room/{self.room_id}/messages").get_json()
        first_latest = first["latest_seq"]

        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "m2"},
        )
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "m3"},
        )

        resp = self.client.get(
            f"/chat/room/{self.room_id}/messages?since={first_latest}"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert [m["message"] for m in data["messages"]] == ["m2", "m3"]

    def test_since_rejects_invalid_value(self):
        resp = self.client.get(f"/chat/room/{self.room_id}/messages?since=abc")
        assert resp.status_code == 400
        assert "Invalid 'since' parameter" in resp.get_json()["error"]

    def test_pruned_through_seq_advances_after_expiry_cleanup(self):
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "expires-soon"},
        )

        with simple_chat_routes.rooms_lock:
            room = simple_chat_routes.chat_rooms[self.room_id]

        with room.lock:
            room.messages[0]["timestamp"] -= datetime.timedelta(minutes=5)

        resp = self.client.get(f"/chat/room/{self.room_id}/messages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["messages"] == []
        assert data["pruned_through_seq"] >= 1
