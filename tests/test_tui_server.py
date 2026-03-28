"""
Unit tests for src.tui.server.ChatServer.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_rate_limit_blocks_after_threshold():
    server = ChatServer(rate_limit_count=2, rate_limit_window=60, start_cleanup_thread=False)
    base = datetime.datetime(2026, 1, 1, 12, 0, 0)

    allowed, retry_after = server._check_rate_limit("user-1", now=base)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = server._check_rate_limit(
        "user-1", now=base + datetime.timedelta(seconds=10)
    )
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = server._check_rate_limit(
        "user-1", now=base + datetime.timedelta(seconds=20)
    )
    assert allowed is False
    assert retry_after > 0


def test_rate_limit_uses_sliding_window():
    server = ChatServer(rate_limit_count=2, rate_limit_window=60, start_cleanup_thread=False)
    base = datetime.datetime(2026, 1, 1, 12, 0, 0)

    server._check_rate_limit("user-2", now=base)
    server._check_rate_limit("user-2", now=base + datetime.timedelta(seconds=10))

    allowed, retry_after = server._check_rate_limit(
        "user-2", now=base + datetime.timedelta(seconds=61)
    )
    assert allowed is True
    assert retry_after == 0


def test_cleanup_rate_limits_removes_stale_entries():
    server = ChatServer(rate_limit_count=2, rate_limit_window=60, start_cleanup_thread=False)
    now = datetime.datetime.now()

    server.user_message_timestamps["stale-user"] = [now - datetime.timedelta(seconds=120)]
    server.user_message_timestamps["active-user"] = [now - datetime.timedelta(seconds=5)]

    server._cleanup_rate_limits()

    assert "stale-user" not in server.user_message_timestamps
    assert "active-user" in server.user_message_timestamps
    assert len(server.user_message_timestamps["active-user"]) == 1


def test_cleanup_old_messages_overwrites_then_removes():
    server = ChatServer(start_cleanup_thread=False)
    now = datetime.datetime.now()
    message_ref = {
        "username": "ShadowFox1234",
        "message": "top-secret",
        "timestamp": now - datetime.timedelta(seconds=server.MESSAGE_LIFETIME + 5),
    }
    server.messages.append(message_ref)

    server._cleanup_old_messages()

    assert server.messages == []
    assert message_ref["message"] == "X" * len("top-secret")
    assert message_ref["username"] == "X" * len("ShadowFox1234")
