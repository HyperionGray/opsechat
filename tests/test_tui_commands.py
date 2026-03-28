"""
Unit tests for TUI slash commands and command protocol handling.
"""

import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tui.client import ChatClient
from src.tui.server import ChatServer


class _FakeSocket:
    """Minimal socket-like object that records sent JSON messages."""

    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def pop_json(self):
        assert self.sent, "No data sent to fake socket"
        raw = self.sent.pop(0).decode("utf-8").strip()
        return json.loads(raw)


class _ServerHarness:
    """
    Minimal object compatible with ChatServer.handle_command.

    This avoids spinning up the real server cleanup thread in unit tests.
    """

    MESSAGE_LIFETIME = 180

    def __init__(self, users=0, messages=0):
        self.lock = threading.Lock()
        self.clients = {object(): "user" for _ in range(users)}
        self.messages = [{"message": "m"} for _ in range(messages)]

    def _send_json(self, client_socket, payload):
        return client_socket.send((json.dumps(payload) + "\n").encode()) > 0


class TestClientCommands:
    def test_help_command_shows_local_help_and_sends_to_server(self):
        client = ChatClient()
        commands = []
        system_messages = []

        client.send_command = lambda cmd: commands.append(cmd) or True
        client.add_message = lambda _u, msg, is_system=False: (
            system_messages.append(msg) if is_system else None
        )

        should_exit = client.handle_command_input("/help")

        assert should_exit is False
        assert commands == ["help"]
        assert any("Commands:" in msg for msg in system_messages)

    def test_status_and_users_commands_forward_to_server(self):
        client = ChatClient()
        commands = []
        client.send_command = lambda cmd: commands.append(cmd) or True

        assert client.handle_command_input("/status") is False
        assert client.handle_command_input("/users") is False
        assert commands == ["status", "users"]

    def test_quit_command_requests_disconnect(self):
        client = ChatClient()
        client.running = True
        sent = []
        cleaned = []

        client.send_command = lambda cmd: sent.append(cmd) or True
        client.cleanup = lambda: cleaned.append(True)

        should_exit = client.handle_command_input("/quit")

        assert should_exit is True
        assert sent == ["quit"]
        assert cleaned == [True]
        assert client.running is False
        assert client.connection_state == "Disconnected"

    def test_unknown_command_reports_error(self):
        client = ChatClient()
        seen = []
        client.add_message = lambda _u, msg, is_system=False: (
            seen.append(msg) if is_system else None
        )

        should_exit = client.handle_command_input("/doesnotexist")

        assert should_exit is False
        assert any("Unknown command" in msg for msg in seen)

    def test_status_server_message_updates_footer_state(self):
        client = ChatClient()
        seen = []
        client.add_message = lambda _u, msg, is_system=False: (
            seen.append(msg) if is_system else None
        )

        client.handle_server_message(
            {
                "type": "status",
                "connected_users": 3,
                "message_count": 7,
                "message_lifetime_seconds": 180,
            }
        )

        assert client.connected_users == 3
        assert any("users=3" in msg for msg in seen)


class TestServerCommands:
    def test_users_command_returns_connected_count(self):
        harness = _ServerHarness(users=2, messages=0)
        sock = _FakeSocket()

        ChatServer.handle_command(harness, sock, "users")
        payload = sock.pop_json()

        assert payload["type"] == "system"
        assert "2 user(s)" in payload["message"]

    def test_status_command_returns_server_snapshot(self):
        harness = _ServerHarness(users=3, messages=5)
        sock = _FakeSocket()

        ChatServer.handle_command(harness, sock, "status")
        payload = sock.pop_json()

        assert payload["type"] == "status"
        assert payload["connected_users"] == 3
        assert payload["message_count"] == 5
        assert payload["message_lifetime_seconds"] == 180

    def test_help_command_returns_available_commands(self):
        harness = _ServerHarness()
        sock = _FakeSocket()

        ChatServer.handle_command(harness, sock, "help")
        payload = sock.pop_json()

        assert payload["type"] == "system"
        assert "/help" in payload["message"]
        assert "/quit" in payload["message"]

    def test_unknown_command_returns_hint(self):
        harness = _ServerHarness()
        sock = _FakeSocket()

        ChatServer.handle_command(harness, sock, "bogus")
        payload = sock.pop_json()

        assert payload["type"] == "system"
        assert "Unknown command" in payload["message"]
