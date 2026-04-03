import json
import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tui.server import ChatServer


class DummySocket:
    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data)


@pytest.fixture
def server():
    chat_server = ChatServer()
    chat_server.running = False
    return chat_server


def test_message_lifetime_is_four_minutes(server):
    assert server.MESSAGE_LIFETIME == 240


def test_validate_message_rejects_non_string(server):
    is_valid, reason, sanitized = server.validate_message(123)
    assert not is_valid
    assert "string" in reason
    assert sanitized == ""


def test_validate_message_sanitizes_html_chars(server):
    is_valid, reason, sanitized = server.validate_message(" <hello&world> ")
    assert is_valid
    assert reason == ""
    assert sanitized == "helloworld"


def test_handle_client_line_rejects_invalid_json(server):
    client = DummySocket()
    server._handle_client_line(client, "User1", "{not-json")
    assert client.sent, "expected protocol error response"
    payload = json.loads(client.sent[-1].decode().strip())
    assert payload["type"] == "error"
    assert payload["error_code"] == "invalid_json"


def test_handle_client_line_rejects_wrong_payload_type(server):
    client = DummySocket()
    server._handle_client_line(client, "User1", json.dumps({"type": "ping"}))
    payload = json.loads(client.sent[-1].decode().strip())
    assert payload["type"] == "error"
    assert payload["error_code"] == "unsupported_type"


def test_handle_client_line_rejects_base64_like_payload(server):
    client = DummySocket()
    long_encoded = "A" * 600
    server._handle_client_line(
        client,
        "User1",
        json.dumps({"type": "message", "message": long_encoded}),
    )
    payload = json.loads(client.sent[-1].decode().strip())
    assert payload["type"] == "error"
    assert payload["error_code"] == "message_rejected"
    assert "encoded binary data" in payload["message"]


def test_handle_client_line_stores_and_broadcasts_valid_message(server, monkeypatch):
    client = DummySocket()
    broadcast_calls = []

    def fake_broadcast(username, message):
        broadcast_calls.append((username, message))

    monkeypatch.setattr(server, "broadcast_message", fake_broadcast)
    server._handle_client_line(
        client,
        "User1",
        json.dumps({"type": "message", "message": " hello <world> "}),
    )

    messages = server.get_messages()
    assert len(messages) == 1
    assert messages[0]["username"] == "User1"
    assert messages[0]["message"] == "hello world"
    assert broadcast_calls == [("User1", "hello world")]

