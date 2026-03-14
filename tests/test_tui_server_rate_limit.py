"""
Tests for TUI ChatServer rate limiting behavior.
"""

import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from tui.server import ChatServer


def test_rate_limit_allows_until_threshold_then_blocks():
    server = ChatServer(rate_limit_count=3, rate_limit_window_seconds=10)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        allowed, retry_after = server._check_rate_limit(client)
        assert allowed is True
        assert retry_after == 0.0

        allowed, _ = server._check_rate_limit(client)
        assert allowed is True
        allowed, _ = server._check_rate_limit(client)
        assert allowed is True

        allowed, retry_after = server._check_rate_limit(client)
        assert allowed is False
        assert retry_after > 0
    finally:
        client.close()
        server.stop()


def test_rate_limit_resets_after_window_expires():
    server = ChatServer(rate_limit_count=2, rate_limit_window_seconds=5)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        assert server._check_rate_limit(client)[0] is True
        assert server._check_rate_limit(client)[0] is True

        with server.lock:
            server.client_message_timestamps[client] = [time.monotonic() - 10]

        allowed, retry_after = server._check_rate_limit(client)
        assert allowed is True
        assert retry_after == 0.0
    finally:
        client.close()
        server.stop()


def test_rate_limit_can_be_disabled():
    server = ChatServer(rate_limit_count=0, rate_limit_window_seconds=1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        for _ in range(100):
            allowed, retry_after = server._check_rate_limit(client)
            assert allowed is True
            assert retry_after == 0.0
    finally:
        client.close()
        server.stop()


def test_rate_limit_notice_protocol_shape():
    server = ChatServer(rate_limit_count=5, rate_limit_window_seconds=60)
    server_socket, client_socket = socket.socketpair()
    try:
        server._send_rate_limit_notice(server_socket, 1.25)
        line = client_socket.recv(4096).decode("utf-8").strip()
        notice = json.loads(line)
        assert notice["type"] == "rate_limited"
        assert "Rate limit exceeded" in notice["message"]
        assert notice["retry_after_seconds"] == 1.25
    finally:
        server_socket.close()
        client_socket.close()
        server.stop()


def test_stop_clears_rate_limit_state():
    server = ChatServer(rate_limit_count=2, rate_limit_window_seconds=10)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server._check_rate_limit(client)
        with server.lock:
            assert client in server.client_message_timestamps
    finally:
        client.close()

    server.stop()
    with server.lock:
        assert server.client_message_timestamps == {}
