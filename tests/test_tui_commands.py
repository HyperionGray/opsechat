import json
import os
import sys

import pytest
import urwid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from tui.client import ChatClient
from tui.server import ChatServer


class DummySocket:
    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data.decode("utf-8"))
        return len(data)


def _last_sent_json(dummy_socket):
    assert dummy_socket.sent, "Expected at least one sent frame"
    payload = dummy_socket.sent[-1].strip()
    return json.loads(payload)


def test_tui_message_lifetime_is_four_minutes():
    server = ChatServer(start_cleanup_thread=False)
    assert server.MESSAGE_LIFETIME == 240


def test_server_help_command_returns_documented_commands():
    server = ChatServer(start_cleanup_thread=False)
    responses, should_disconnect = server.process_command("help")

    assert should_disconnect is False
    assert len(responses) == 1
    assert responses[0]["type"] == "system"
    assert "/status" in responses[0]["message"]
    assert "/quit" in responses[0]["message"]


def test_server_status_command_returns_structured_status():
    server = ChatServer(start_cleanup_thread=False)
    responses, should_disconnect = server.process_command("status")

    assert should_disconnect is False
    assert len(responses) == 1
    status = responses[0]
    assert status["type"] == "status"
    assert "connected_users" in status
    assert "messages_in_memory" in status
    assert "uptime_seconds" in status
    assert status["message_lifetime_seconds"] == 240


def test_server_users_command_uses_connected_client_count():
    server = ChatServer(start_cleanup_thread=False)
    fake_sock_1 = object()
    fake_sock_2 = object()
    with server.lock:
        server.clients[fake_sock_1] = "A"
        server.clients[fake_sock_2] = "B"

    responses, should_disconnect = server.process_command("users")

    assert should_disconnect is False
    assert responses[0]["type"] == "system"
    assert responses[0]["message"] == "Connected users: 2"


def test_server_quit_command_requests_disconnect():
    server = ChatServer(start_cleanup_thread=False)
    responses, should_disconnect = server.process_command("quit")

    assert should_disconnect is True
    assert responses[0]["type"] == "system"
    assert "Disconnecting" in responses[0]["message"]


def test_client_sends_command_for_slash_status():
    client = ChatClient()
    client.socket = DummySocket()

    client.send_message("/status")
    sent = _last_sent_json(client.socket)

    assert sent["type"] == "command"
    assert sent["command"] == "status"


def test_client_sends_chat_payload_for_normal_message():
    client = ChatClient()
    client.socket = DummySocket()

    client.send_message("hello world")
    sent = _last_sent_json(client.socket)

    assert sent["type"] == "message"
    assert sent["message"] == "hello world"


def test_client_quit_command_exits_mainloop():
    client = ChatClient()
    client.socket = DummySocket()

    with pytest.raises(urwid.ExitMainLoop):
        client.send_message("/quit")

    sent = _last_sent_json(client.socket)
    assert sent["type"] == "command"
    assert sent["command"] == "quit"
