"""
Unit tests for TUI chat server controls.
"""

import os
import sys

# Ensure src/ is importable when tests run from repository root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from tui.server import ChatServer


def test_message_lifetime_is_four_minutes():
    assert ChatServer.MESSAGE_LIFETIME == 240


def test_rate_limit_blocks_after_threshold():
    server = ChatServer()
    username = "RateLimitUser"

    for _ in range(server.RATE_LIMIT_MESSAGES):
        allowed, retry_after = server._check_rate_limit(username)
        assert allowed is True
        assert retry_after == 0

    allowed, retry_after = server._check_rate_limit(username)
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_isolated_per_username():
    server = ChatServer()
    limited_user = "UserA"
    fresh_user = "UserB"

    for _ in range(server.RATE_LIMIT_MESSAGES):
        allowed, _ = server._check_rate_limit(limited_user)
        assert allowed is True

    blocked, _ = server._check_rate_limit(limited_user)
    allowed, retry_after = server._check_rate_limit(fresh_user)

    assert blocked is False
    assert allowed is True
    assert retry_after == 0


def test_status_payload_contains_runtime_limits():
    server = ChatServer()
    with server.lock:
        server.messages = [
            {"username": "one", "message": "hello", "timestamp": None},
            {"username": "two", "message": "world", "timestamp": None},
        ]
        server.clients = {object(): "one", object(): "two"}

    status = server._build_status_message()

    assert status["type"] == "status"
    assert status["connected_users"] == 2
    assert status["buffered_messages"] == 2
    assert status["message_lifetime_seconds"] == 240
    assert status["rate_limit"]["max_messages"] == ChatServer.RATE_LIMIT_MESSAGES
    assert status["rate_limit"]["window_seconds"] == ChatServer.RATE_LIMIT_WINDOW_SECONDS
