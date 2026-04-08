"""
Unit tests for TUI chat server rate limiting and validation behavior.
"""

import datetime
from collections import deque

from src.tui.server import ChatServer


def test_tui_rate_limit_blocks_after_threshold():
    server = ChatServer(
        message_rate_limit_count=2,
        message_rate_limit_window_seconds=30,
    )
    username = "RateLimitUser0001"

    assert server.add_message(username, "first message") is True
    assert server.add_message(username, "second message") is True
    assert server.add_message(username, "third message should be blocked") is False
    assert len(server.messages) == 2


def test_tui_rate_limit_is_per_user():
    server = ChatServer(
        message_rate_limit_count=1,
        message_rate_limit_window_seconds=30,
    )

    assert server.add_message("UserOne0001", "first from user one") is True
    assert server.add_message("UserOne0001", "second from user one blocked") is False
    assert server.add_message("UserTwo0002", "first from user two allowed") is True

    usernames = [msg["username"] for msg in server.messages]
    assert usernames == ["UserOne0001", "UserTwo0002"]


def test_tui_rate_limit_expired_entries_are_pruned():
    server = ChatServer(
        message_rate_limit_count=2,
        message_rate_limit_window_seconds=10,
    )
    username = "PruneUser0003"
    old_time = datetime.datetime.now() - datetime.timedelta(seconds=60)

    server.user_message_timestamps[username] = deque([old_time, old_time])
    assert server.add_message(username, "allowed after old entries expire") is True
    assert len(server.user_message_timestamps[username]) == 1


def test_tui_rejects_likely_base64_payload():
    server = ChatServer(message_rate_limit_count=100, message_rate_limit_window_seconds=30)
    username = "ValidationUser0004"
    likely_b64 = "A" * 700 + "=="

    assert server.add_message(username, likely_b64) is False
    assert len(server.messages) == 0
