"""
Unit tests for TUI server rate limiting and bounded history behavior.
"""

import datetime

from src.tui.server import ChatServer


def _fresh_server() -> ChatServer:
    server = ChatServer()
    server.running = False
    with server.lock:
        server.messages.clear()
        server.clients.clear()
        server.user_message_timestamps.clear()
    return server


def test_rate_limit_blocks_after_threshold():
    server = _fresh_server()
    username = "RateUser1234"

    for _ in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, retry_after = server._check_user_rate_limit(username)
        assert allowed is True
        assert retry_after == 0

    allowed, retry_after = server._check_user_rate_limit(username)
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_resets_after_window():
    server = _fresh_server()
    username = "WindowReset5678"
    base_time = datetime.datetime(2026, 1, 1, 12, 0, 0)

    for _ in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, retry_after = server._check_user_rate_limit(username, now=base_time)
        assert allowed is True
        assert retry_after == 0

    blocked, _ = server._check_user_rate_limit(username, now=base_time)
    assert blocked is False

    next_window_time = base_time + datetime.timedelta(seconds=server.RATE_LIMIT_WINDOW_SECONDS + 1)
    allowed, retry_after = server._check_user_rate_limit(username, now=next_window_time)
    assert allowed is True
    assert retry_after == 0


def test_server_history_is_bounded():
    server = _fresh_server()

    original_limit = server.MAX_STORED_MESSAGES
    server.MAX_STORED_MESSAGES = 3
    try:
        server.add_message("UserA", "m1")
        oldest_reference = server.messages[0]
        server.add_message("UserA", "m2")
        server.add_message("UserA", "m3")
        server.add_message("UserA", "m4")

        assert len(server.messages) == 3
        assert [msg["message"] for msg in server.messages] == ["m2", "m3", "m4"]
        # Confirm removed messages are overwritten before deletion.
        assert oldest_reference["message"] == "XX"
        assert oldest_reference["username"] == "XXXXX"
    finally:
        server.MAX_STORED_MESSAGES = original_limit
