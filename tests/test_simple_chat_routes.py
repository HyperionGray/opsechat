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
    chat_rooms,
    direct_messages,
    rooms_lock,
    dm_lock,
    _rate_limit_lock,
    _rate_limit_store,
    _rate_limit_violations,
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


@pytest.fixture(autouse=True)
def reset_simple_chat_state():
    """Ensure in-memory stores are reset between tests."""
    with rooms_lock:
        chat_rooms.clear()
    with dm_lock:
        direct_messages.clear()
    with _rate_limit_lock:
        _rate_limit_store.clear()
        _rate_limit_violations.clear()

    yield

    with rooms_lock:
        chat_rooms.clear()
    with dm_lock:
        direct_messages.clear()
    with _rate_limit_lock:
        _rate_limit_store.clear()
        _rate_limit_violations.clear()


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

    def test_post_message_rate_limit_includes_retry_metadata(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        limit = RATE_LIMITS["chat_message"]["max_requests"]

        for i in range(limit):
            response = client.post(
                f"/chat/room/{room_id}/messages",
                json={"message": f"msg-{i}"},
                content_type="application/json",
            )
            assert response.status_code == 200

        limited = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "overflow"},
            content_type="application/json",
        )
        assert limited.status_code == 429
        data = limited.get_json()
        assert isinstance(data.get("retry_after"), int)
        assert data["retry_after"] >= 1
        assert limited.headers.get("Retry-After") == str(data["retry_after"])

    def test_repeated_rate_limit_hits_increase_backoff(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        limit = RATE_LIMITS["chat_message"]["max_requests"]

        for i in range(limit):
            response = client.post(
                f"/chat/room/{room_id}/messages",
                json={"message": f"msg-{i}"},
                content_type="application/json",
            )
            assert response.status_code == 200

        first_limited = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "overflow-1"},
            content_type="application/json",
        )
        second_limited = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "overflow-2"},
            content_type="application/json",
        )

        assert first_limited.status_code == 429
        assert second_limited.status_code == 429
        first_retry = first_limited.get_json()["retry_after"]
        second_retry = second_limited.get_json()["retry_after"]
        assert second_retry >= first_retry

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
