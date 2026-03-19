#!/usr/bin/env python3
"""
Unit tests for TUI server core behavior.
"""

import time

from src.tui.server import ChatServer


def test_message_lifetime_is_four_minutes():
    """Messages should burn after 4 minutes (240s)."""
    server = ChatServer()
    assert server.MESSAGE_LIFETIME == 240


def test_add_message_sanitizes_and_returns_clean_content():
    """Messages are sanitized before storing/broadcasting."""
    server = ChatServer()
    accepted, payload = server.add_message("UserA", " <b>Hello & welcome</b> ")
    assert accepted is True
    assert payload == "bHello  welcome/b"
    stored = server.get_messages()
    assert len(stored) == 1
    assert stored[0]["message"] == "bHello  welcome/b"


def test_add_message_rejects_probable_base64_payload():
    """Large base64-like payloads should be rejected."""
    server = ChatServer()
    suspicious = "A" * 600
    accepted, error = server.add_message("UserA", suspicious)
    assert accepted is False
    assert "encoded/binary" in error


def test_per_client_rate_limit_blocks_and_recovers():
    """A client should be throttled after exceeding configured threshold."""
    server = ChatServer(rate_limit_messages=2, rate_limit_window_seconds=1)
    client_id = object()

    allowed_1, retry_after_1 = server._check_and_record_rate_limit(client_id)
    allowed_2, retry_after_2 = server._check_and_record_rate_limit(client_id)
    allowed_3, retry_after_3 = server._check_and_record_rate_limit(client_id)

    assert allowed_1 is True and retry_after_1 == 0
    assert allowed_2 is True and retry_after_2 == 0
    assert allowed_3 is False
    assert retry_after_3 >= 1

    time.sleep(1.1)
    allowed_4, retry_after_4 = server._check_and_record_rate_limit(client_id)
    assert allowed_4 is True
    assert retry_after_4 == 0


def test_rate_limit_is_per_client_not_global():
    """One noisy client should not throttle another client."""
    server = ChatServer(rate_limit_messages=1, rate_limit_window_seconds=10)
    client_a = object()
    client_b = object()

    assert server._check_and_record_rate_limit(client_a)[0] is True
    assert server._check_and_record_rate_limit(client_a)[0] is False
    assert server._check_and_record_rate_limit(client_b)[0] is True
