"""
Focused pytest coverage for recent chat and email features.
"""

import datetime
import secrets


def test_secure_ids():
    """Cryptographically secure IDs should be unique and long enough."""
    from simple_chat_routes import generate_secure_room_id, generate_secure_dm_id

    room_ids = {generate_secure_room_id() for _ in range(100)}
    dm_ids = {generate_secure_dm_id() for _ in range(100)}

    assert len(room_ids) == 100
    assert len(dm_ids) == 100
    assert len(generate_secure_room_id()) > 40


def test_chat_room_key():
    """Each room should get its own encryption key."""
    from simple_chat_routes import ChatRoom

    room = ChatRoom("test_room_123")
    room2 = ChatRoom("test_room_456")

    key = room.get_room_key()
    key2 = room2.get_room_key()

    assert key
    assert len(key) > 40
    assert key != key2


def test_rate_limiting():
    """Email sender rate limiting should enforce max sends per hour."""
    from email_system import burner_manager

    user_id = f"test_rate_limit_{datetime.datetime.now().timestamp()}"

    allowed, _ = burner_manager.check_send_rate_limit(user_id)
    assert allowed

    for _ in range(10):
        burner_manager.record_sent_email(user_id)

    status = burner_manager.get_send_limit_status(user_id)
    assert status["sends_used"] == 10
    assert status["sends_remaining"] == 0

    allowed, message = burner_manager.check_send_rate_limit(user_id)
    assert not allowed
    assert "Rate limit exceeded" in message


def test_base64_detection_heuristic():
    """Long, space-poor payloads should be detected as base64-like."""

    def detect_base64(message):
        if len(message) > 100:
            return message.count(" ") < len(message) * 0.05
        return False

    assert not detect_base64("This is a normal message with spaces and punctuation.")
    assert detect_base64("A" * 150)
    assert not detect_base64("A " * 60)
    assert not detect_base64("SGVsbG8gV29ybGQ=")


def test_message_length_cap():
    """Message max length should remain 500 chars."""
    from simple_chat_routes import MAX_MESSAGE_LENGTH

    assert MAX_MESSAGE_LENGTH == 500
    assert len("A" * 501) > MAX_MESSAGE_LENGTH
    assert len("A" * 500) == MAX_MESSAGE_LENGTH


def test_dm_structure_round_trip():
    """Direct message entries should be writable/retrievable under the DM lock."""
    from simple_chat_routes import direct_messages, dm_lock

    dm_id = secrets.token_urlsafe(16)
    test_dm = {
        "dm_id": dm_id,
        "sender_id": "test_sender",
        "sender_name": "TestUser",
        "room_id": "test_room_abc123",
        "message": "Join me in the secure room!",
        "timestamp": datetime.datetime.now(),
        "read": False,
    }

    with dm_lock:
        direct_messages[dm_id] = test_dm

    with dm_lock:
        retrieved = direct_messages.get(dm_id)
        assert retrieved is not None
        assert retrieved["room_id"] == "test_room_abc123"
        assert retrieved["read"] is False
        retrieved["read"] = True
        del direct_messages[dm_id]
