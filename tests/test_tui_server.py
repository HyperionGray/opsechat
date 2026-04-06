"""
Focused unit tests for src.tui.server.ChatServer command handling.
"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from tui.server import ChatServer


class DummySocket:
    """Minimal socket stub that captures sent data."""

    def __init__(self):
        self.payloads = []

    def send(self, data):
        self.payloads.append(data.decode("utf-8"))
        return len(data)

    def close(self):
        return


def test_help_command_returns_system_message():
    server = ChatServer()
    client = DummySocket()

    handled = server.handle_command("Alice", "/help", client)

    assert handled is True
    assert client.payloads, "Expected at least one system payload"
    assert '"type": "system"' in client.payloads[-1]
    assert "/users" in client.payloads[-1]
    server.stop()


def test_users_command_reports_connected_clients():
    server = ChatServer()
    client = DummySocket()

    with server.lock:
        server.clients[client] = "Alice"

    handled = server.handle_command("Alice", "/users", client)

    assert handled is True
    assert "Connected users: 1" in client.payloads[-1]
    server.stop()


def test_non_command_message_is_not_handled_as_command():
    server = ChatServer()
    client = DummySocket()

    handled = server.handle_command("Alice", "hello world", client)

    assert handled is False
    assert not client.payloads
    server.stop()


def test_unknown_command_returns_hint():
    server = ChatServer()
    client = DummySocket()

    handled = server.handle_command("Alice", "/nope", client)

    assert handled is True
    assert "Unknown command '/nope'" in client.payloads[-1]
    assert "/help" in client.payloads[-1]
    server.stop()


def test_stats_command_reports_burn_policy():
    server = ChatServer()
    client = DummySocket()

    handled = server.handle_command("Alice", "/stats", client)

    assert handled is True
    assert "burn_after=" in client.payloads[-1]
    assert f"burn_after={server.MESSAGE_LIFETIME}s" in client.payloads[-1]
    server.stop()
