"""
Tests for TUI slash command handling in client/server modules.
"""

import json
import os
import sys
import threading
import time

import pytest

# Ensure src/ is importable for tui.* modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_ROOT)

pytest.importorskip("urwid")
pytest.importorskip("socks")
import urwid

from tui.client import ChatClient
from tui.server import ChatServer


class _FakeSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def close(self):
        self.closed = True


def _last_message_text(client: ChatClient) -> str:
    widget = client.messages_walker[-1]
    text, _ = widget.get_text()
    return text


def test_help_command_displays_available_commands():
    client = ChatClient()
    client.handle_command("/help")
    text = _last_message_text(client)
    assert "Commands: /help, /status, /users, /quit" in text


def test_status_command_reports_connection_context():
    client = ChatClient(host="127.0.0.1", port=5555, use_tor=True)
    client.running = True
    client.socket = _FakeSocket()
    client.connected_at = time.time() - 5
    client.username = "TestUser"

    client.handle_command("/status")
    text = _last_message_text(client)

    assert "Status: Connected" in text
    assert "Server: 127.0.0.1:5555" in text
    assert "Tor: on" in text
    assert "Username: TestUser" in text


def test_users_command_sends_command_payload_to_server():
    client = ChatClient()
    fake_socket = _FakeSocket()
    client.socket = fake_socket

    client.handle_command("/users")

    assert len(fake_socket.sent) == 1
    payload = json.loads(fake_socket.sent[0].decode("utf-8").strip())
    assert payload["type"] == "command"
    assert payload["command"] == "/users"


def test_quit_command_exits_main_loop():
    client = ChatClient()
    with pytest.raises(urwid.ExitMainLoop):
        client.handle_command("/quit")


def test_server_users_command_returns_aggregate_count_only():
    server = ChatServer.__new__(ChatServer)
    server.lock = threading.Lock()

    requester = _FakeSocket()
    other = _FakeSocket()
    server.clients = {requester: "UserA", other: "UserB"}

    server._handle_command(requester, "/users")

    assert requester.sent, "Expected a response for /users command"
    payload = json.loads(requester.sent[-1].decode("utf-8").strip())
    assert payload["type"] == "system"
    assert payload["message"] == "Connected users: 2"


def test_server_unknown_command_returns_help_hint():
    server = ChatServer.__new__(ChatServer)
    server.lock = threading.Lock()
    server.clients = {}

    requester = _FakeSocket()
    server._handle_command(requester, "/nope")

    payload = json.loads(requester.sent[-1].decode("utf-8").strip())
    assert payload["type"] == "system"
    assert "Unknown command '/nope'" in payload["message"]
    assert "/users" in payload["message"]
