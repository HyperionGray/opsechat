#!/usr/bin/env python3
"""
Unit tests for TUI ChatServer rate limiting.
"""

import datetime
import os
import sys

import pytest


# Add repository src/ to path for imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tui.server import ChatServer


@pytest.fixture
def server():
    chat_server = ChatServer(
        rate_limit_max_messages=2,
        rate_limit_window_seconds=30,
    )
    try:
        yield chat_server
    finally:
        chat_server.stop()


def test_rate_limit_blocks_after_max_messages(server):
    user = "RateTestUser"
    base = datetime.datetime(2026, 1, 1, 0, 0, 0)

    first = server.check_rate_limit(user, now=base)
    second = server.check_rate_limit(user, now=base + datetime.timedelta(seconds=1))
    blocked = server.check_rate_limit(user, now=base + datetime.timedelta(seconds=2))

    assert first["allowed"] is True
    assert second["allowed"] is True
    assert blocked["allowed"] is False
    assert blocked["retry_after_seconds"] > 0


def test_rate_limit_window_expiry_allows_messages_again(server):
    user = "WindowResetUser"
    base = datetime.datetime(2026, 1, 1, 0, 0, 0)

    server.check_rate_limit(user, now=base)
    server.check_rate_limit(user, now=base + datetime.timedelta(seconds=1))
    blocked = server.check_rate_limit(user, now=base + datetime.timedelta(seconds=2))
    allowed_after_window = server.check_rate_limit(
        user,
        now=base + datetime.timedelta(seconds=31),
    )

    assert blocked["allowed"] is False
    assert allowed_after_window["allowed"] is True


def test_stop_clears_rate_limit_state(server):
    server.check_rate_limit("CleanupUser", now=datetime.datetime(2026, 1, 1, 0, 0, 0))
    assert "CleanupUser" in server.message_rate_history

    server.stop()

    assert server.message_rate_history == {}
