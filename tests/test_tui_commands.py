import json

import pytest
import urwid

from src.tui.client import ChatClient
from src.tui.server import ChatServer


class _SocketCapture:
    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data.decode("utf-8"))
        return len(data)


def _decode_sent_json_lines(socket_capture):
    payload = "".join(socket_capture.sent)
    lines = [line for line in payload.split("\n") if line]
    return [json.loads(line) for line in lines]


def test_server_help_command_returns_supported_commands():
    server = ChatServer(start_cleanup_thread=False)
    fake_client = _SocketCapture()

    keep_connected = server._handle_command(fake_client, "/help")

    assert keep_connected is True
    responses = _decode_sent_json_lines(fake_client)
    assert responses[0]["type"] == "command_response"
    assert responses[0]["command"] == "help"
    assert "/status" in responses[0]["data"]["commands"]


def test_server_status_command_returns_diagnostics():
    server = ChatServer(host="127.0.0.1", port=6666, start_cleanup_thread=False)
    fake_client = _SocketCapture()

    keep_connected = server._handle_command(fake_client, "/status")

    assert keep_connected is True
    response = _decode_sent_json_lines(fake_client)[0]
    assert response["command"] == "status"
    assert response["success"] is True
    assert response["data"]["host"] == "127.0.0.1"
    assert response["data"]["port"] == 6666
    assert response["data"]["message_lifetime_seconds"] == server.MESSAGE_LIFETIME


def test_server_users_command_reports_connected_count():
    server = ChatServer(start_cleanup_thread=False)
    fake_client = _SocketCapture()
    with server.lock:
        server.clients[object()] = "SwiftRaven0001"
        server.clients[object()] = "ShadowFox0002"

    keep_connected = server._handle_command(fake_client, "/users")

    assert keep_connected is True
    response = _decode_sent_json_lines(fake_client)[0]
    assert response["command"] == "users"
    assert response["data"]["connected_users"] == 2


def test_server_quit_command_requests_disconnect():
    server = ChatServer(start_cleanup_thread=False)
    fake_client = _SocketCapture()

    keep_connected = server._handle_command(fake_client, "/quit")

    assert keep_connected is False
    response = _decode_sent_json_lines(fake_client)[0]
    assert response["command"] == "quit"
    assert response["disconnect"] is True


def test_client_enter_routes_slash_input_to_command():
    client = ChatClient()
    seen = {"message": None, "command": None}
    client.send_message = lambda msg: seen.update({"message": msg})
    client.send_command = lambda cmd: seen.update({"command": cmd})
    client.input_box.set_edit_text("/users")

    client.handle_input("enter")

    assert seen["command"] == "/users"
    assert seen["message"] is None
    assert client.input_box.get_edit_text() == ""


def test_client_quit_command_exits_main_loop():
    client = ChatClient()
    client.send_command = lambda cmd: None
    client.input_box.set_edit_text("/quit")

    with pytest.raises(urwid.ExitMainLoop):
        client.handle_input("enter")
