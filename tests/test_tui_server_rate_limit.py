import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_message_lifetime_matches_tui_docs():
    server = ChatServer()
    try:
        assert server.MESSAGE_LIFETIME == 240
    finally:
        server.stop()


def test_rate_limit_allows_messages_within_window():
    server = ChatServer()
    client_sock, peer_sock = socket.socketpair()
    try:
        for _ in range(server.RATE_LIMIT_COUNT):
            assert server._is_rate_limited(client_sock) is False
    finally:
        client_sock.close()
        peer_sock.close()
        server.stop()


def test_rate_limit_blocks_after_threshold():
    server = ChatServer()
    client_sock, peer_sock = socket.socketpair()
    try:
        for _ in range(server.RATE_LIMIT_COUNT):
            assert server._is_rate_limited(client_sock) is False

        assert server._is_rate_limited(client_sock) is True
    finally:
        client_sock.close()
        peer_sock.close()
        server.stop()


def test_send_system_error_emits_error_type_payload():
    server = ChatServer()
    client_sock, peer_sock = socket.socketpair()
    try:
        server.send_system_error(client_sock, "rate limited")
        data = peer_sock.recv(4096).decode("utf-8").strip()

        assert '"type": "error"' in data
        assert '"message": "rate limited"' in data
    finally:
        client_sock.close()
        peer_sock.close()
        server.stop()
