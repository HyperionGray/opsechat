"""
Unit tests for TUI chat server core behavior.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_message_lifetime_is_four_minutes():
    server = ChatServer()
    assert server.MESSAGE_LIFETIME == 240


def test_rate_limit_blocks_message_burst():
    server = ChatServer(rate_limit_messages=2, rate_limit_window_seconds=60)

    assert server.add_message("user-a", "one") is True
    assert server.add_message("user-a", "two") is True
    assert server.add_message("user-a", "three") is False

    reason = server.get_rejection_reason("user-a")
    assert reason is not None
    assert "Rate limit exceeded" in reason


def test_rate_limit_is_per_user():
    server = ChatServer(rate_limit_messages=1, rate_limit_window_seconds=60)

    assert server.add_message("user-a", "one") is True
    assert server.add_message("user-a", "two") is False

    # Different user should still be allowed.
    assert server.add_message("user-b", "hello") is True


def test_rate_limit_window_expiry_allows_new_message():
    server = ChatServer(rate_limit_messages=1, rate_limit_window_seconds=60)
    now = time.time()
    server.user_message_timestamps["user-a"] = [now - 120]

    assert server.add_message("user-a", "fresh") is True


def test_sanitization_empty_message_sets_reason():
    server = ChatServer()

    assert server.add_message("user-a", "<><>") is False
    reason = server.get_rejection_reason("user-a")
    assert reason == "Message became empty after sanitization."
