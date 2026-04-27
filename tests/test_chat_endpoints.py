"""
Integration tests for the simple chat HTTP endpoints.

These tests focus on the closed-roster OpenPGP alpha flow: room creation,
immutable epoch bootstrap, envelope storage, and the deprecated shared-key
endpoint.
"""

import datetime
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from closed_roster_room import OPENPGP_ENVELOPE_TYPE
from simple_chat_routes import chat_rooms, direct_messages, dm_lock, rooms_lock


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
    return {
        "member_id": member_id,
        "display_name": display_name or member_id.title(),
        "signing_fingerprint": _fp(f"{member_id}-sign"),
        "encryption_fingerprint": _fp(f"{member_id}-enc"),
        "signing_key_id": _key_id(f"{member_id}-sign-key"),
        "encryption_key_id": _key_id(f"{member_id}-enc-key"),
        "public_key_armored": _public_key(member_id),
    }


def _bootstrap_payload(room_state: dict, sender_member_id: str = "alice") -> dict:
    epoch = room_state["active_epoch"]
    sender = next(member for member in epoch["members"] if member["member_id"] == sender_member_id)
    return {
        "envelope_type": OPENPGP_ENVELOPE_TYPE,
        "room_id": epoch["room_id"],
        "epoch": epoch["epoch"],
        "sender_member_id": sender["member_id"],
        "sender_signing_fingerprint": sender["signing_fingerprint"],
        "roster_hash": epoch["roster_hash"],
        "recipient_encryption_fingerprints": [
            member["encryption_fingerprint"] for member in epoch["members"]
        ],
        "intended_recipient_fingerprints": [
            member["encryption_fingerprint"] for member in epoch["members"]
        ],
        "recipient_encryption_key_ids": [
            member["encryption_key_id"] for member in epoch["members"]
        ],
        "armored_message": "-----BEGIN PGP MESSAGE-----\nopaque\n-----END PGP MESSAGE-----",
    }


def _fresh_app():
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


class TestChatCreateEndpoint:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def test_create_room_returns_success_and_url(self):
        response = self.client.post("/chat/create")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["room_url"].startswith("/chat/room/")

    def test_created_room_exposes_closed_roster_state(self):
        room_id = self.client.post("/chat/create").get_json()["room_id"]
        state = self.client.get(f"/chat/room/{room_id}/state")
        data = state.get_json()
        assert state.status_code == 200
        assert data["mode"] == OPENPGP_ENVELOPE_TYPE
        assert data["active_epoch"] is None


class TestClosedRosterBootstrapAndMessages:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()
        self.room_id = self.client.post("/chat/create").get_json()["room_id"]

    def test_bootstrap_returns_immutable_epoch(self):
        response = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["active_epoch"]["epoch"] == 1
        assert data["active_epoch"]["immutable_roster"] is True

    def test_second_bootstrap_is_rejected(self):
        self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        )
        response = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("carol")],
            },
        )
        assert response.status_code == 400
        assert "already initialized" in response.get_json()["error"]

    def test_messages_reject_plaintext_before_bootstrap(self):
        response = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json={"message": "plaintext"},
        )
        assert response.status_code == 409
        assert "Bootstrap" in response.get_json()["error"]

    def test_messages_accept_valid_envelope_after_bootstrap(self):
        state = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        ).get_json()
        response = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json=_bootstrap_payload(state),
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_messages_reject_sender_mismatch(self):
        state = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        ).get_json()
        payload = _bootstrap_payload(state)
        payload["sender_signing_fingerprint"] = _fp("unexpected")
        response = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json=payload,
        )
        assert response.status_code == 400
        assert "sender signing fingerprint mismatch" in response.get_json()["error"]

    def test_messages_reject_recipient_key_id_mismatch(self):
        state = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        ).get_json()
        payload = _bootstrap_payload(state)
        payload["recipient_encryption_key_ids"] = payload["recipient_encryption_key_ids"][:1]
        response = self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json=payload,
        )
        assert response.status_code == 400
        assert "recipient encryption key ids do not match" in response.get_json()["error"]

    def test_messages_endpoint_returns_envelope_metadata(self):
        state = self.client.post(
            f"/chat/room/{self.room_id}/state/bootstrap",
            json={
                "creator_member_id": "alice",
                "members": [_member_record("alice"), _member_record("bob")],
            },
        ).get_json()
        self.client.post(
            f"/chat/room/{self.room_id}/messages",
            json=_bootstrap_payload(state),
        )
        response = self.client.get(f"/chat/room/{self.room_id}/messages")
        data = response.get_json()
        assert response.status_code == 200
        assert len(data["messages"]) == 1
        message = data["messages"][0]
        assert message["message_type"] == OPENPGP_ENVELOPE_TYPE
        assert message["sender_member_id"] == "alice"
        assert message["armored_message"].startswith("-----BEGIN PGP MESSAGE-----")


class TestDeprecatedRoomKeyEndpoint:
    def setup_method(self):
        _clear_rooms()
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def test_key_endpoint_returns_410(self):
        room_id = self.client.post("/chat/create").get_json()["room_id"]
        response = self.client.get(f"/chat/room/{room_id}/key")
        assert response.status_code == 410
        data = response.get_json()
        assert data["deprecated"] is True
        assert data["mode"] == OPENPGP_ENVELOPE_TYPE

    def test_key_endpoint_missing_room_still_404s(self):
        response = self.client.get("/chat/room/no-room-here/key")
        assert response.status_code == 404


class TestDMEndpoints:
    def setup_method(self):
        _clear_rooms()
        _clear_dms()
        self.app = _fresh_app()
        self.client = self.app.test_client()
        self.room_id = self.client.post("/chat/create").get_json()["room_id"]

    def test_send_dm_success(self):
        response = self.client.post(
            "/chat/dm/send",
            json={"room_id": self.room_id, "message": "join my room"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "dm_id" in data
        assert data["expires_in"] == 60

    def test_expired_dm_returns_404(self):
        with dm_lock:
            direct_messages["expired"] = {
                "dm_id": "expired",
                "sender_id": "u1",
                "sender_name": "Alice",
                "room_id": self.room_id,
                "message": "old invite",
                "timestamp": datetime.datetime.now() - datetime.timedelta(seconds=90),
                "read": False,
            }
        response = self.client.get("/chat/dm/expired")
        assert response.status_code == 404
