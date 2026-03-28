#!/usr/bin/env python3
"""
Unit tests for TUI server message rate limiting behavior.
"""

import sys
import pathlib
import datetime


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tui.server import ChatServer


def test_tui_rate_limit_blocks_after_threshold():
    server = ChatServer()
    try:
        username = "RateLimitUser0001"

        for i in range(server.RATE_LIMIT_MAX_MESSAGES):
            result = server.submit_message(username, f"msg-{i}")
            assert result["accepted"] is True

        blocked = server.submit_message(username, "one-too-many")
        assert blocked["accepted"] is False
        assert blocked["error"] == "rate_limited"
        assert blocked["retry_after"] >= 1
    finally:
        server.stop()


def test_tui_rate_limit_isolated_per_user():
    server = ChatServer()
    try:
        user_a = "UserA0001"
        user_b = "UserB0002"

        for i in range(server.RATE_LIMIT_MAX_MESSAGES):
            assert server.submit_message(user_a, f"a-{i}")["accepted"] is True

        blocked = server.submit_message(user_a, "a-over")
        assert blocked["accepted"] is False
        assert blocked["error"] == "rate_limited"

        allowed_b = server.submit_message(user_b, "b-1")
        assert allowed_b["accepted"] is True
    finally:
        server.stop()


def test_tui_rate_limit_cleanup_removes_stale_entries():
    server = ChatServer()
    try:
        username = "StaleUser0003"
        assert server.submit_message(username, "hello")["accepted"] is True
        assert username in server.message_rate_limits

        old_ts = datetime.datetime.now() - datetime.timedelta(
            seconds=server.RATE_LIMIT_WINDOW_SECONDS + 5
        )
        with server.lock:
            server.message_rate_limits[username] = [old_ts]

        server._cleanup_rate_limits()
        assert username not in server.message_rate_limits
    finally:
        server.stop()


def test_submit_message_broadcasts_sanitized_content():
    server = ChatServer()
    captured = []

    def _capture(username, message):
        captured.append((username, message))

    server.broadcast_message = _capture
    try:
        result = server.submit_message("CleanUser0004", "<hello>&world")
        assert result["accepted"] is True
        assert captured == [("CleanUser0004", "helloworld")]

        stored = server.get_messages()
        assert len(stored) == 1
        assert stored[0]["message"] == "helloworld"
    finally:
        server.stop()
