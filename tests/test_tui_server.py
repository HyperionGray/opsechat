"""
Focused unit tests for src/tui/server.py.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from tui.server import ChatServer


def test_tui_server_message_lifetime_is_four_minutes():
    server = ChatServer()
    try:
        assert server.MESSAGE_LIFETIME == 240
    finally:
        server.stop()


def test_tui_server_rate_limit_blocks_after_threshold():
    server = ChatServer()
    username = "RateLimitUser0001"
    try:
        for i in range(server.RATE_LIMIT_MAX_MESSAGES):
            assert server.add_message(username, f"msg-{i}") is True

        assert server.add_message(username, "one-too-many") is False
        reason = server.get_last_rejection_reason(username)
        assert "Rate limit exceeded" in reason
    finally:
        server.stop()


def test_tui_server_rate_limit_resets_after_window():
    server = ChatServer()
    username = "RateLimitUser0002"
    try:
        old = datetime.datetime.now() - datetime.timedelta(
            seconds=server.RATE_LIMIT_WINDOW_SECONDS + 1
        )
        with server.lock:
            server.user_message_times[username] = [old] * server.RATE_LIMIT_MAX_MESSAGES

        assert server.add_message(username, "allowed-after-window") is True
    finally:
        server.stop()
