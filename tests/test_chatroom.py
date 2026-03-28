"""
Unit tests for the ChatRoom class, room-level cleanup, and DM (direct message)
unit logic in simple_chat_routes.

Related GitHub issues: #109 (initial chat/email plan), #112 (release push with
full testing), #114 (simple web-app rooms), #116 (automated key exchange, DMs),
#118 (final functionality tests) — ephemeral rooms, 3-minute message expiry,
memory overwriting, automated key exchange, DM expiry.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_chat_routes import (
    ChatRoom,
    cleanup_old_dms,
    cleanup_old_rooms,
    chat_rooms,
    direct_messages,
    dm_lock,
    rooms_lock,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_rooms():
    with rooms_lock:
        chat_rooms.clear()


def _clear_dms():
    with dm_lock:
        direct_messages.clear()


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
# Direct message unit tests
# ===========================================================================

class TestDirectMessageCleanup:
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
        assert dm["sender_name"] == "X" * len("Alice")
        assert dm["sender_id"] == "X" * len("u1")
