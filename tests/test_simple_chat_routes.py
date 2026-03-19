"""
Tests for simple_chat_routes.py

Covers: room creation, messaging, direct messages, room key exchange,
        input validation, rate-limit logic, and helper utilities.
"""
import pytest
from unittest.mock import patch
from app_factory import create_app
from simple_chat_routes import (
    generate_secure_room_id,
    generate_secure_dm_id,
    generate_random_username,
    get_random_color_rgb,
    ChatRoom,
    check_rate_limit,
    RATE_LIMITS,
    MAX_MESSAGE_LENGTH,
    CHAT_MESSAGE_LIFETIME_SECONDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a test Flask application."""
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    """Return a test client with a fresh request context."""
    with app.test_client() as c:
        with app.app_context():
            yield c


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_secure_room_id_length(self):
        rid = generate_secure_room_id(32)
        # token_urlsafe(32) produces a 43-char base64url string
        assert len(rid) > 0

    def test_generate_secure_room_id_unique(self):
        ids = {generate_secure_room_id(32) for _ in range(50)}
        assert len(ids) == 50  # all unique

    def test_generate_secure_dm_id_unique(self):
        ids = {generate_secure_dm_id() for _ in range(50)}
        assert len(ids) == 50

    def test_generate_random_username_format(self):
        username = generate_random_username()
        # Should contain at least one digit
        assert any(c.isdigit() for c in username)
        assert len(username) > 4

    def test_get_random_color_rgb_structure(self):
        color = get_random_color_rgb()
        assert isinstance(color, list)
        assert len(color) == 3
        for channel in color:
            assert 0 <= channel <= 255


# ---------------------------------------------------------------------------
# ChatRoom class
# ---------------------------------------------------------------------------

class TestChatRoom:
    def test_add_and_get_messages(self):
        room = ChatRoom("test-room")
        room.add_message("u1", "Alice", [255, 0, 0], "hello world")
        msgs = room.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["message"] == "hello world"
        assert msgs[0]["username"] == "Alice"

    def test_user_count_increments(self):
        room = ChatRoom("test-room")
        assert room.get_user_count() == 0
        room.add_message("u1", "Alice", [255, 0, 0], "hi")
        assert room.get_user_count() == 1
        room.add_message("u2", "Bob", [0, 255, 0], "hey")
        assert room.get_user_count() == 2
        # Same user again – count should remain 2
        room.add_message("u1", "Alice", [255, 0, 0], "again")
        assert room.get_user_count() == 2

    def test_room_key_is_base64(self):
        import base64
        room = ChatRoom("test-room")
        key = room.get_room_key()
        # Should not raise
        decoded = base64.b64decode(key)
        assert len(decoded) == 32

    def test_cleanup_old_messages(self):
        import datetime
        room = ChatRoom("test-room")
        room.add_message("u1", "Alice", [255, 0, 0], "old message")
        # Force the message timestamp to be old
        with room.lock:
            room.messages[0]["timestamp"] -= datetime.timedelta(minutes=10)
        room.cleanup_old_messages()
        assert room.get_messages() == []

    def test_get_status_includes_burn_metadata(self):
        room = ChatRoom("test-room")
        empty_status = room.get_status()
        assert empty_status["message_count"] == 0
        assert empty_status["next_burn_in_seconds"] is None
        assert empty_status["message_ttl_seconds"] == CHAT_MESSAGE_LIFETIME_SECONDS

        room.add_message("u1", "Alice", [255, 0, 0], "hello")
        status = room.get_status()
        assert status["message_count"] == 1
        assert status["user_count"] == 1
        assert isinstance(status["next_burn_in_seconds"], int)
        assert 0 <= status["next_burn_in_seconds"] <= CHAT_MESSAGE_LIFETIME_SECONDS


# ---------------------------------------------------------------------------
# Rate-limit helper
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def test_allows_within_limit(self):
        allowed, _ = check_rate_limit("sess-001", "chat_message")
        assert allowed is True

    def test_blocks_when_exceeded(self):
        session_id = "sess-ratelimit-test"
        limit = RATE_LIMITS["chat_create"]["max_requests"]
        for _ in range(limit):
            check_rate_limit(session_id, "chat_create")
        allowed, retry_after = check_rate_limit(session_id, "chat_create")
        assert allowed is False
        assert retry_after > 0

    def test_unknown_endpoint_always_allowed(self):
        allowed, _ = check_rate_limit("sess-002", "nonexistent_endpoint")
        assert allowed is True


# ---------------------------------------------------------------------------
# HTTP routes – chat rooms
# ---------------------------------------------------------------------------

class TestChatRoutes:
    def test_chat_index_returns_200(self, client):
        response = client.get("/chat")
        assert response.status_code == 200

    def test_create_room_returns_success(self, client):
        response = client.post("/chat/create")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "room_id" in data
        assert data["room_url"].startswith("/chat/room/")

    def test_create_room_id_unique(self, client):
        r1 = client.post("/chat/create").get_json()["room_id"]
        r2 = client.post("/chat/create").get_json()["room_id"]
        assert r1 != r2

    def test_join_nonexistent_room_returns_404(self, client):
        response = client.get("/chat/room/nonexistent-room-id-xyz")
        assert response.status_code == 404

    def test_join_existing_room_returns_200(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}")
        assert response.status_code == 200

    def test_get_messages_empty_room(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}/messages")
        assert response.status_code == 200
        data = response.get_json()
        assert data["messages"] == []
        assert isinstance(data["user_count"], int)
        assert "status" in data
        assert data["status"]["message_count"] == 0
        assert data["status"]["next_burn_in_seconds"] is None

    def test_room_status_endpoint_returns_room_metadata(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "hello world"},
            content_type="application/json",
        )

        response = client.get(f"/chat/room/{room_id}/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["room_id"] == room_id
        assert data["message_count"] == 1
        assert data["user_count"] >= 1
        assert data["message_ttl_seconds"] == CHAT_MESSAGE_LIFETIME_SECONDS
        assert isinstance(data["next_burn_in_seconds"], int)
        assert 0 <= data["next_burn_in_seconds"] <= CHAT_MESSAGE_LIFETIME_SECONDS

    def test_room_status_endpoint_missing_room(self, client):
        response = client.get("/chat/room/no-such-room/status")
        assert response.status_code == 404

    def test_post_message_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "hello world"},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_post_message_missing_body(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        # Sending no body with JSON content-type produces a 400; without
        # content-type Flask returns 415 Unsupported Media Type – both are errors.
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_post_message_empty_string(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_post_message_too_long(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        long_msg = "a " * (MAX_MESSAGE_LENGTH + 1)
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": long_msg},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_post_message_to_nonexistent_room(self, client):
        response = client.post(
            "/chat/room/no-such-room/messages",
            json={"message": "hello"},
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_get_room_key_returns_key(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}/key")
        assert response.status_code == 200
        data = response.get_json()
        assert "encryption_key" in data
        assert len(data["encryption_key"]) > 0

    def test_get_room_key_nonexistent_room(self, client):
        response = client.get("/chat/room/no-such-room/key")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# HTTP routes – direct messages
# ---------------------------------------------------------------------------

class TestDMRoutes:
    def test_send_dm_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.post(
            "/chat/dm/send",
            json={"room_id": room_id, "message": "join me here"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "dm_id" in data

    def test_send_dm_missing_fields(self, client):
        response = client.post(
            "/chat/dm/send",
            json={"room_id": "some-room"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_send_dm_message_too_long(self, client):
        response = client.post(
            "/chat/dm/send",
            json={"room_id": "some-room", "message": "x" * 201},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_view_dm_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        dm_id = client.post(
            "/chat/dm/send",
            json={"room_id": room_id, "message": "hello"},
            content_type="application/json",
        ).get_json()["dm_id"]

        response = client.get(f"/chat/dm/{dm_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["room_id"] == room_id

    def test_view_dm_nonexistent(self, client):
        response = client.get("/chat/dm/nonexistent-dm-id")
        assert response.status_code == 404

    def test_view_dm_expired(self, client):
        import datetime
        from simple_chat_routes import direct_messages, dm_lock

        room_id = client.post("/chat/create").get_json()["room_id"]
        dm_id = client.post(
            "/chat/dm/send",
            json={"room_id": room_id, "message": "ephemeral"},
            content_type="application/json",
        ).get_json()["dm_id"]

        # Force the DM timestamp to be old
        with dm_lock:
            direct_messages[dm_id]["timestamp"] -= datetime.timedelta(minutes=5)

        response = client.get(f"/chat/dm/{dm_id}")
        assert response.status_code == 404
