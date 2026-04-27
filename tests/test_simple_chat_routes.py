"""
Tests for simple_chat_routes.py.

Covers: room creation, immutable closed-roster bootstrap, encrypted message
envelope acceptance, direct messages, room page wiring, and helper utilities.
"""

import datetime
import hashlib
import pytest

import simple_chat_routes
from app_factory import create_app
from closed_roster_room import OPENPGP_ENVELOPE_TYPE
from simple_chat_routes import (
    ChatRoom,
    MAX_MESSAGE_LENGTH,
    RATE_LIMITS,
    check_rate_limit,
    generate_random_username,
    generate_secure_dm_id,
    generate_secure_room_id,
    get_random_color_rgb,
)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()


def _key_id(seed: str) -> str:
    return _fp(seed)[:16]


def _public_key(seed: str) -> str:
    return (
        "-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
        f"{seed}\n"
        "-----END PGP PUBLIC KEY BLOCK-----"
    )


def _member_record(member_id: str, display_name: str | None = None) -> dict:
    name = display_name or member_id.title()
    return {
        "member_id": member_id,
        "display_name": name,
        "signing_fingerprint": _fp(f"{member_id}-sign"),
        "encryption_fingerprint": _fp(f"{member_id}-enc"),
        "signing_key_id": _key_id(f"{member_id}-sign-key"),
        "encryption_key_id": _key_id(f"{member_id}-enc-key"),
        "public_key_armored": _public_key(member_id),
    }


def _bootstrap_room(client, room_id: str, members: list[dict] | None = None) -> dict:
    roster = members or [_member_record("alice"), _member_record("bob")]
    response = client.post(
        f"/chat/room/{room_id}/state/bootstrap",
        json={"creator_member_id": "alice", "members": roster},
        content_type="application/json",
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _message_payload(room_state: dict, sender_member_id: str = "alice") -> dict:
    epoch = room_state["active_epoch"]
    sender = next(member for member in epoch["members"] if member["member_id"] == sender_member_id)
    recipient_fps = [member["encryption_fingerprint"] for member in epoch["members"]]
    recipient_key_ids = [member["encryption_key_id"] for member in epoch["members"]]
    return {
        "envelope_type": OPENPGP_ENVELOPE_TYPE,
        "room_id": epoch["room_id"],
        "epoch": epoch["epoch"],
        "sender_member_id": sender["member_id"],
        "sender_signing_fingerprint": sender["signing_fingerprint"],
        "roster_hash": epoch["roster_hash"],
        "recipient_encryption_fingerprints": recipient_fps,
        "intended_recipient_fingerprints": recipient_fps,
        "recipient_encryption_key_ids": recipient_key_ids,
        "armored_message": "-----BEGIN PGP MESSAGE-----\nopaque\n-----END PGP MESSAGE-----",
    }


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        with app.app_context():
            yield test_client


class TestHelpers:
    def test_generate_secure_room_id_unique(self):
        ids = {generate_secure_room_id(32) for _ in range(50)}
        assert len(ids) == 50

    def test_generate_secure_dm_id_unique(self):
        ids = {generate_secure_dm_id() for _ in range(50)}
        assert len(ids) == 50

    def test_generate_random_username_format(self):
        username = generate_random_username()
        assert any(char.isdigit() for char in username)
        assert len(username) > 4

    def test_get_random_color_rgb_structure(self):
        color = get_random_color_rgb()
        assert isinstance(color, list)
        assert len(color) == 3
        assert all(0 <= channel <= 255 for channel in color)


class TestChatRoom:
    def test_add_and_get_legacy_message_for_internal_unit_coverage(self):
        room = ChatRoom("test-room")
        room.add_message("u1", "Alice", [255, 0, 0], "hello world")
        messages = room.get_messages()
        assert len(messages) == 1
        assert messages[0]["message"] == "hello world"
        assert messages[0]["message_type"] == "legacy_plaintext_test_only"

    def test_bootstrap_closed_roster_state(self):
        room = ChatRoom("test-room")
        state = room.bootstrap_closed_roster([_member_record("alice"), _member_record("bob")])
        assert state["active_epoch"]["epoch"] == 1
        assert state["active_epoch"]["immutable_roster"] is True
        assert len(state["active_epoch"]["members"]) == 2

    def test_cleanup_old_messages_removes_expired_entries(self):
        room = ChatRoom("test-room")
        room.add_message("u1", "Alice", [255, 0, 0], "old message")
        with room.lock:
            room.messages[0]["timestamp"] -= datetime.timedelta(minutes=10)
        room.cleanup_old_messages()
        assert room.get_messages() == []


class TestCheckRateLimit:
    def test_allows_within_limit(self):
        allowed, retry_after = check_rate_limit("sess-001", "chat_message")
        assert allowed is True
        assert retry_after == 0

    def test_blocks_when_exceeded(self):
        session_id = "sess-ratelimit-test"
        limit = RATE_LIMITS["chat_create"]["max_requests"]
        for _ in range(limit):
            check_rate_limit(session_id, "chat_create")
        allowed, retry_after = check_rate_limit(session_id, "chat_create")
        assert allowed is False
        assert retry_after > 0

    def test_unknown_endpoint_always_allowed(self):
        allowed, retry_after = check_rate_limit("sess-002", "unknown")
        assert allowed is True
        assert retry_after == 0


class TestChatRoutes:
    def test_chat_index_returns_200(self, client):
        response = client.get("/chat")
        assert response.status_code == 200
        body = response.data.decode()
        assert "closed-roster OpenPGP".lower() in body.lower()

    def test_create_room_returns_success(self, client):
        response = client.post("/chat/create")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["room_url"].startswith("/chat/room/")

    def test_join_existing_room_returns_200(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}")
        assert response.status_code == 200
        body = response.data.decode()
        assert "openpgp.min.js" in body
        assert f'data-room-id="{room_id}"' in body

    def test_room_state_initially_has_no_active_epoch(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}/state")
        data = response.get_json()
        assert response.status_code == 200
        assert data["active_epoch"] is None
        assert data["policy"]["immutable_roster"] is True
        assert data["policy"]["shared_room_keys_supported"] is False

    def test_bootstrap_room_state_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        state = _bootstrap_room(client, room_id)
        assert state["success"] is True
        assert state["active_epoch"]["epoch"] == 1
        assert state["active_epoch"]["immutable_roster"] is True

    def test_bootstrap_room_state_rejects_second_bootstrap(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        _bootstrap_room(client, room_id)
        response = client.post(
            f"/chat/room/{room_id}/state/bootstrap",
            json={"creator_member_id": "alice", "members": [_member_record("alice")]},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "already initialized" in response.get_json()["error"]

    def test_post_message_requires_bootstrap(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": "plaintext"},
            content_type="application/json",
        )
        assert response.status_code == 409
        assert "Bootstrap" in response.get_json()["error"]

    def test_post_closed_roster_message_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        room_state = _bootstrap_room(client, room_id)
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json=_message_payload(room_state),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_post_closed_roster_message_rejects_recipient_mismatch(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        room_state = _bootstrap_room(client, room_id)
        payload = _message_payload(room_state)
        payload["recipient_encryption_fingerprints"] = [payload["recipient_encryption_fingerprints"][0]]
        response = client.post(
            f"/chat/room/{room_id}/messages",
            json=payload,
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "recipient set does not match" in response.get_json()["error"]

    def test_get_messages_returns_envelope_fields(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        room_state = _bootstrap_room(client, room_id)
        client.post(
            f"/chat/room/{room_id}/messages",
            json=_message_payload(room_state),
            content_type="application/json",
        )
        response = client.get(f"/chat/room/{room_id}/messages")
        assert response.status_code == 200
        data = response.get_json()
        assert data["messages"]
        message = data["messages"][0]
        for field in (
            "message_type",
            "armored_message",
            "sender_member_id",
            "sender_signing_fingerprint",
            "epoch",
            "roster_hash",
            "timestamp",
        ):
            assert field in message

    def test_room_key_endpoint_is_deprecated(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}/key")
        assert response.status_code == 410
        data = response.get_json()
        assert data["deprecated"] is True
        assert data["mode"] == OPENPGP_ENVELOPE_TYPE

    def test_room_page_has_no_inline_script(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}")
        body = response.data.decode()
        assert "chat-room.js" in body
        assert "openpgp.min.js" in body
        assert "addEventListener" not in body
        assert "<style>" not in body
        assert "onclick=" not in body

    def test_message_input_maxlength_matches_constant(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        response = client.get(f"/chat/room/{room_id}")
        body = response.data.decode()
        assert f'maxlength="{MAX_MESSAGE_LENGTH}"' in body


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

    def test_view_dm_success(self, client):
        room_id = client.post("/chat/create").get_json()["room_id"]
        dm_id = client.post(
            "/chat/dm/send",
            json={"room_id": room_id, "message": "hello"},
            content_type="application/json",
        ).get_json()["dm_id"]
        response = client.get(f"/chat/dm/{dm_id}")
        assert response.status_code == 200
        assert response.get_json()["room_id"] == room_id

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

    def test_view_dm_expired(self, client):
        from simple_chat_routes import direct_messages, dm_lock

        room_id = client.post("/chat/create").get_json()["room_id"]
        dm_id = client.post(
            "/chat/dm/send",
            json={"room_id": room_id, "message": "ephemeral"},
            content_type="application/json",
        ).get_json()["dm_id"]

        with dm_lock:
            direct_messages[dm_id]["timestamp"] -= datetime.timedelta(minutes=5)

        response = client.get(f"/chat/dm/{dm_id}")
        assert response.status_code == 404
