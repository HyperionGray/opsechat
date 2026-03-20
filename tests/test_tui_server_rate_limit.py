"""
Unit tests for TUI server rate limiting behavior.
"""

import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_tui_message_lifetime_is_four_minutes():
    assert ChatServer.MESSAGE_LIFETIME == 240


def test_tui_rate_limit_allows_up_to_capacity():
    server = ChatServer()
    now = 1000.0

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, retry_after = server._check_rate_limit("user-a", now_ts=now + i)
        assert allowed is True
        assert retry_after == 0


def test_tui_rate_limit_blocks_when_exceeded():
    server = ChatServer()
    now = 2000.0

    for _ in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, _ = server._check_rate_limit("user-b", now_ts=now)
        assert allowed is True

    allowed, retry_after = server._check_rate_limit("user-b", now_ts=now)
    assert allowed is False
    assert 1 <= retry_after <= server.RATE_LIMIT_WINDOW_SECONDS


def test_tui_rate_limit_resets_after_window():
    server = ChatServer()
    now = 3000.0

    for _ in range(server.RATE_LIMIT_MAX_MESSAGES):
        server._check_rate_limit("user-c", now_ts=now)

    allowed, retry_after = server._check_rate_limit(
        "user-c",
        now_ts=now + server.RATE_LIMIT_WINDOW_SECONDS + 1,
    )
    assert allowed is True
    assert retry_after == 0


def test_tui_rate_limit_is_per_user():
    server = ChatServer()
    now = 4000.0

    for _ in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, _ = server._check_rate_limit("user-d", now_ts=now)
        assert allowed is True

    blocked, _ = server._check_rate_limit("user-d", now_ts=now)
    allowed_other, retry_after_other = server._check_rate_limit("user-e", now_ts=now)

    assert blocked is False
    assert allowed_other is True
    assert retry_after_other == 0
