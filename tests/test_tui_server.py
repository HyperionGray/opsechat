"""
Unit tests for the TUI chat server logic.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_message_lifetime_is_four_minutes():
    server = ChatServer()
    assert server.MESSAGE_LIFETIME == 240


def test_add_message_applies_html_sanitization():
    server = ChatServer()
    username = "TestUser0001"

    assert server.add_message(username, "<hello>&world>") is True
    messages = server.get_messages()
    assert len(messages) == 1
    assert messages[0]["message"] == "helloworld"


def test_rate_limit_blocks_after_window_capacity():
    server = ChatServer()
    username = "RateLimitUser0001"

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        assert server.add_message(username, f"message-{i}") is True

    # The next message should be blocked within the same window.
    assert server.add_message(username, "blocked-message") is False


def test_rate_limit_is_per_user():
    server = ChatServer()
    user_a = "UserA0001"
    user_b = "UserB0001"

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        assert server.add_message(user_a, f"a-{i}") is True

    # User A is now limited, but user B should still be able to send.
    assert server.add_message(user_a, "a-blocked") is False
    assert server.add_message(user_b, "b-allowed") is True


def test_rate_limit_allows_after_window_expires():
    server = ChatServer()
    username = "WindowUser0001"

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        assert server.add_message(username, f"msg-{i}") is True
    assert server.add_message(username, "blocked") is False

    # Force timestamps to be stale, then retry.
    with server.lock:
        server.user_message_timestamps[username] = [
            datetime.datetime.now()
            - datetime.timedelta(seconds=server.RATE_LIMIT_WINDOW_SECONDS + 1)
            for _ in server.user_message_timestamps[username]
        ]

    assert server.add_message(username, "allowed-after-window") is True
