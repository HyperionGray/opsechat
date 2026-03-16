#!/usr/bin/env python3
"""Tests for TUI control commands and slash-command behavior."""

import json

import pytest
import urwid

from src.tui.client import ChatClient
from src.tui.server import ChatServer


class FakeSocket:
    """Small fake socket for capturing outgoing bytes."""

    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def close(self):
        return None


def _decode_last_payload(fake_socket):
    raw = fake_socket.sent[-1].decode("utf-8").strip()
    return json.loads(raw)


def test_server_users_control_command_returns_client_count():
    """Server should return current connected user count."""
    server = ChatServer()
    requester = FakeSocket()
    peer = FakeSocket()

    with server.lock:
        server.clients = {
            requester: "UserA",
            peer: "UserB",
        }

    server.handle_control_command(requester, "users")
    response = _decode_last_payload(requester)

    assert response["type"] == "control_response"
    assert response["command"] == "users"
    assert response["users"] == 2


def test_server_status_control_command_returns_snapshot():
    """Server should include message/user/lifetime metadata in status."""
    server = ChatServer()
    requester = FakeSocket()

    with server.lock:
        server.clients = {requester: "UserA"}

    assert server.add_message("UserA", "hello")
    server.handle_control_command(requester, "status")
    response = _decode_last_payload(requester)

    assert response["type"] == "control_response"
    assert response["command"] == "status"
    assert response["users"] == 1
    assert response["message_count"] >= 1
    assert response["message_lifetime"] == ChatServer.MESSAGE_LIFETIME
    assert response["uptime_seconds"] >= 0


def test_client_users_command_sends_control_payload():
    """Client /users should send a control command to the server."""
    client = ChatClient()
    fake_socket = FakeSocket()
    client.socket = fake_socket
    client.running = True

    client.execute_command("/users")
    payload = _decode_last_payload(fake_socket)

    assert payload == {"type": "control", "command": "users"}


def test_client_encrypt_command_toggles_footer_state():
    """Client /encrypt should toggle local encryption indicator state."""
    client = ChatClient()

    client.execute_command("/encrypt on")
    assert client.encryption_enabled is True

    client.execute_command("/encrypt off")
    assert client.encryption_enabled is False


def test_client_quit_command_exits_main_loop():
    """Client /quit should request loop exit."""
    client = ChatClient()
    client.running = True

    with pytest.raises(urwid.ExitMainLoop):
        client.execute_command("/quit")
