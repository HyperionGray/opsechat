"""
Tests for TUI server rate limiting behavior.
"""

import time

from src.tui.server import ChatServer


def test_tui_message_lifetime_is_four_minutes():
    """TUI server should retain messages for 4 minutes."""
    assert ChatServer.MESSAGE_LIFETIME == 240


def test_rate_limit_blocks_excess_messages_and_recovers():
    """A user should be throttled after hitting the per-window cap."""
    server = ChatServer(start_cleanup_thread=False)
    server.RATE_LIMIT_MAX_MESSAGES = 2
    server.RATE_LIMIT_WINDOW_SECONDS = 1

    assert server.add_message_with_result("alice", "first")["ok"] is True
    assert server.add_message_with_result("alice", "second")["ok"] is True

    blocked = server.add_message_with_result("alice", "third")
    assert blocked["ok"] is False
    assert blocked["error"] == "rate_limited"
    assert blocked["retry_after"] > 0

    time.sleep(1.05)
    assert server.add_message_with_result("alice", "after-window")["ok"] is True


def test_rate_limit_is_scoped_per_user():
    """One noisy user should not block other users."""
    server = ChatServer(start_cleanup_thread=False)
    server.RATE_LIMIT_MAX_MESSAGES = 1
    server.RATE_LIMIT_WINDOW_SECONDS = 2

    assert server.add_message_with_result("alice", "hello")["ok"] is True
    assert server.add_message_with_result("bob", "hello from bob")["ok"] is True

    blocked = server.add_message_with_result("alice", "spam")
    assert blocked["ok"] is False
    assert blocked["error"] == "rate_limited"
