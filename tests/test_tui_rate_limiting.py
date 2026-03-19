"""
Unit tests for TUI chat server rate limiting.
"""

import datetime
import os
import socket
import sys

# Ensure src package imports work in test runs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from tui.server import ChatServer


def test_tui_rate_limit_blocks_after_threshold():
    server = ChatServer(rate_limit_count=2, rate_limit_window_seconds=60)

    allowed, retry_after = server._check_rate_limit("UserA")
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = server._check_rate_limit("UserA")
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = server._check_rate_limit("UserA")
    assert allowed is False
    assert retry_after >= 1


def test_tui_rate_limit_resets_after_window():
    server = ChatServer(rate_limit_count=2, rate_limit_window_seconds=10)
    now = datetime.datetime.now()

    with server.lock:
        server.user_message_timestamps["UserA"] = [
            now - datetime.timedelta(seconds=11),
            now - datetime.timedelta(seconds=10.5),
        ]

    allowed, retry_after = server._check_rate_limit("UserA")
    assert allowed is True
    assert retry_after == 0


def test_rate_limit_cleanup_prunes_disconnected_users():
    server = ChatServer(rate_limit_count=2, rate_limit_window_seconds=60)
    now = datetime.datetime.now()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        with server.lock:
            server.clients[client_socket] = "ConnectedUser"
            server.user_message_timestamps["ConnectedUser"] = [now]
            server.user_message_timestamps["DisconnectedUser"] = [now]

        with server.lock:
            server._cleanup_rate_limit_state(now)

        assert "ConnectedUser" in server.user_message_timestamps
        assert "DisconnectedUser" not in server.user_message_timestamps
    finally:
        client_socket.close()
