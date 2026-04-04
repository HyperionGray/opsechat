"""
Unit tests for TUI chat server rate limiting and validation behavior.
"""

from src.tui.server import ChatServer


def test_check_message_rate_limit_allows_until_threshold():
    server = ChatServer()
    client_id = "client-allow"
    base_ts = 1_000.0

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, retry_after = server._check_message_rate_limit(client_id, now=base_ts + i)
        assert allowed is True
        assert retry_after == 0


def test_check_message_rate_limit_blocks_when_threshold_exceeded():
    server = ChatServer()
    client_id = "client-block"
    base_ts = 2_000.0

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, _ = server._check_message_rate_limit(client_id, now=base_ts + i)
        assert allowed is True

    allowed, retry_after = server._check_message_rate_limit(
        client_id,
        now=base_ts + server.RATE_LIMIT_MAX_MESSAGES
    )
    assert allowed is False
    assert retry_after > 0


def test_check_message_rate_limit_allows_again_after_window():
    server = ChatServer()
    client_id = "client-window"
    base_ts = 3_000.0

    for i in range(server.RATE_LIMIT_MAX_MESSAGES):
        allowed, _ = server._check_message_rate_limit(client_id, now=base_ts + i)
        assert allowed is True

    blocked, retry_after = server._check_message_rate_limit(
        client_id,
        now=base_ts + server.RATE_LIMIT_MAX_MESSAGES
    )
    assert blocked is False
    assert retry_after > 0

    allowed_again, retry_after = server._check_message_rate_limit(
        client_id,
        now=base_ts + server.RATE_LIMIT_WINDOW_SECONDS + 2
    )
    assert allowed_again is True
    assert retry_after == 0


def test_message_validation_rejects_base64_like_payload():
    server = ChatServer()
    username = "TestUser"
    base64_like = "A" * 600

    accepted = server.add_message(username, base64_like)
    assert accepted is False
    assert server.get_messages() == []
