"""
Unit tests for src.tui.server.ChatServer.

Focuses on unfinished TUI work: per-user message rate limiting and
user-facing system messages.
"""

import json
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def _make_server(**kwargs):
    return ChatServer(start_cleanup_thread=False, **kwargs)


def test_add_message_accepts_until_limit_then_blocks():
    server = _make_server(rate_limit_max_messages=2, rate_limit_window_seconds=30)

    ok1, reason1 = server.add_message_with_reason("user-a", "first")
    ok2, reason2 = server.add_message_with_reason("user-a", "second")
    ok3, reason3 = server.add_message_with_reason("user-a", "third")

    assert ok1 is True and reason1 is None
    assert ok2 is True and reason2 is None
    assert ok3 is False and reason3 == "rate_limited"
    assert len(server.get_messages()) == 2


def test_rate_limit_is_per_user_not_global():
    server = _make_server(rate_limit_max_messages=1, rate_limit_window_seconds=30)

    ok1, reason1 = server.add_message_with_reason("user-a", "hello")
    ok2, reason2 = server.add_message_with_reason("user-b", "world")

    assert ok1 is True and reason1 is None
    assert ok2 is True and reason2 is None
    assert len(server.get_messages()) == 2


def test_rate_limit_message_contains_config_values():
    server = _make_server(rate_limit_max_messages=7, rate_limit_window_seconds=11)

    message = server.get_rate_limit_message()

    assert "max 7 messages" in message
    assert "11 seconds" in message


def test_handle_client_sends_system_message_when_rate_limited(monkeypatch):
    server = _make_server(rate_limit_max_messages=1, rate_limit_window_seconds=30)
    server.running = True

    fixed_username = "RateUser0001"
    monkeypatch.setattr(server, "generate_username", lambda: fixed_username)

    client_socket, server_side_socket = socket.socketpair()
    try:
        # Two messages quickly: first accepted, second should be rate-limited.
        payload = (
            json.dumps({"type": "message", "message": "m1"}) + "\n" +
            json.dumps({"type": "message", "message": "m2"}) + "\n"
        ).encode("utf-8")
        client_socket.sendall(payload)
        client_socket.shutdown(socket.SHUT_WR)

        server.handle_client(server_side_socket, ("local", 0))

        raw = client_socket.recv(65536).decode("utf-8")
        messages = [
            json.loads(line)
            for line in raw.splitlines()
            if line.strip()
        ]

        assert any(m.get("type") == "welcome" for m in messages)
        assert any(
            m.get("type") == "system" and "Rate limit exceeded" in m.get("message", "")
            for m in messages
        )
    finally:
        client_socket.close()
