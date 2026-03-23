"""
Unit tests for TUI server message rate limiting.
"""

import datetime

from src.tui.server import ChatServer


def _build_server(limit: int = 2, window_seconds: int = 60) -> ChatServer:
    server = ChatServer()
    server.MAX_MESSAGES_PER_WINDOW = limit
    server.RATE_LIMIT_WINDOW_SECONDS = window_seconds
    return server


def test_rate_limit_applies_per_user():
    server = _build_server(limit=2, window_seconds=60)
    try:
        assert server.add_message("alice", "first")
        assert server.add_message("alice", "second")
        assert not server.add_message("alice", "third")
    finally:
        server.stop()


def test_rate_limit_does_not_block_other_users():
    server = _build_server(limit=1, window_seconds=60)
    try:
        assert server.add_message("alice", "first")
        assert not server.add_message("alice", "second")
        assert server.add_message("bob", "hello from bob")
    finally:
        server.stop()


def test_rate_limit_resets_after_window():
    server = _build_server(limit=1, window_seconds=30)
    try:
        ok, error = server.add_message_with_error("alice", "first")
        assert ok is True
        assert error is None

        with server.lock:
            server._message_timestamps["alice"] = [
                datetime.datetime.now() - datetime.timedelta(seconds=31)
            ]

        ok, error = server.add_message_with_error("alice", "second")
        assert ok is True
        assert error is None
    finally:
        server.stop()


def test_add_message_with_error_returns_rate_limited_code():
    server = _build_server(limit=1, window_seconds=60)
    try:
        ok, error = server.add_message_with_error("alice", "first")
        assert ok is True
        assert error is None

        ok, error = server.add_message_with_error("alice", "second")
        assert ok is False
        assert error == "rate_limited"
    finally:
        server.stop()
