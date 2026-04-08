"""
Protocol-level tests for src.tui.server ChatServer.

Focus: explicit error feedback for invalid client packets and message sanitization.
"""

import datetime
from src.tui.server import ChatServer


class DummySocket:
    """Minimal socket stub that records payloads sent by ChatServer."""

    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data.decode("utf-8"))
        return len(data)


def test_validate_message_rejects_empty_and_non_text():
    server = ChatServer()
    assert server.validate_message("") == "Message cannot be empty"
    assert server.validate_message("   ") == "Message cannot be empty"
    assert server.validate_message(None) == "Message must be text"


def test_validate_message_rejects_oversized_and_encoded_payload():
    server = ChatServer()
    assert server.validate_message("a" * 1001) == "Message too long (max 1000 chars)"
    assert (
        server.validate_message("A" * 600)
        == "Message appears to be encoded/binary data and was rejected"
    )


def test_send_error_emits_error_packet():
    server = ChatServer()
    sock = DummySocket()

    server.send_error(sock, "validation_error", "Message cannot be empty")

    assert len(sock.sent) == 1
    payload = sock.sent[0]
    assert '"type": "error"' in payload
    assert '"error_code": "validation_error"' in payload
    assert '"message": "Message cannot be empty"' in payload


def test_add_message_sanitizes_and_stores():
    server = ChatServer()
    ok = server.add_message("Alice", "<hello>&world>")
    assert ok is True

    messages = server.get_messages()
    assert len(messages) == 1
    assert messages[0]["username"] == "Alice"
    assert messages[0]["message"] == "helloworld"


def test_cleanup_old_messages_overwrites_expired_content():
    server = ChatServer()
    server.add_message("Bob", "secret")

    with server.lock:
        old_ref = server.messages[0]
        old_ref["timestamp"] = datetime.datetime.now() - datetime.timedelta(minutes=10)

    server._cleanup_old_messages()

    assert old_ref["message"] == "X" * len("secret")
    assert old_ref["username"] == "X" * len("Bob")
    assert server.get_messages() == []
