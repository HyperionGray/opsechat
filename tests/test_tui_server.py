"""
Unit tests for TUI server protocol and validation behavior.
"""

import json
import socket
from pathlib import Path

import pytest

# Ensure local src/ package is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO_ROOT))

from src.tui import server as tui_server
from src.tui.server import ChatServer


@pytest.fixture
def chat_server():
    """Create a ChatServer instance for unit tests."""
    server = ChatServer(host="127.0.0.1", port=5555)
    yield server
    server.stop()


def test_status_payload_contains_limits(chat_server):
    payload = chat_server._build_status_payload()
    assert payload["type"] == "status"
    assert payload["message_lifetime_seconds"] == chat_server.MESSAGE_LIFETIME
    assert payload["max_message_length"] == chat_server.MAX_MESSAGE_LENGTH
    assert (
        payload["rate_limit_messages_per_window"]
        == chat_server.RATE_LIMIT_MESSAGES_PER_WINDOW
    )
    assert payload["rate_limit_window_seconds"] == chat_server.RATE_LIMIT_WINDOW_SECONDS


def test_validate_message_content_rejections(chat_server):
    ok, code, message, sanitized = chat_server.validate_message_content("")
    assert not ok
    assert code == "empty_message"
    assert sanitized is None

    long_message = "a" * (chat_server.MAX_MESSAGE_LENGTH + 1)
    ok, code, message, sanitized = chat_server.validate_message_content(long_message)
    assert not ok
    assert code == "message_too_long"
    assert "max" in message.lower()
    assert sanitized is None


def test_validate_message_content_sanitizes_html(chat_server):
    ok, code, message, sanitized = chat_server.validate_message_content(
        "<b>Hello & world</b>"
    )
    assert ok
    assert code == ""
    assert message == ""
    assert sanitized == "bHello  world/b"


def test_rate_limit_enforced_and_recovers(chat_server, monkeypatch):
    client_key = object()
    now = [1000.0]

    monkeypatch.setattr(tui_server.time, "time", lambda: now[0])

    for _ in range(chat_server.RATE_LIMIT_MESSAGES_PER_WINDOW):
        allowed, retry_after = chat_server._check_rate_limit(client_key)
        assert allowed
        assert retry_after == 0

    allowed, retry_after = chat_server._check_rate_limit(client_key)
    assert not allowed
    assert retry_after >= 1

    now[0] += chat_server.RATE_LIMIT_WINDOW_SECONDS + 1
    allowed, retry_after = chat_server._check_rate_limit(client_key)
    assert allowed
    assert retry_after == 0


def test_send_error_emits_protocol_event(chat_server):
    sender, receiver = socket.socketpair()
    try:
        chat_server.send_error(
            sender,
            code="message_too_long",
            message="Message too long (max 1000 chars).",
            extra={"retry_after_seconds": 2},
        )
        raw = receiver.recv(4096).decode("utf-8").strip()
        payload = json.loads(raw)
        assert payload["type"] == "error"
        assert payload["code"] == "message_too_long"
        assert "Message too long" in payload["message"]
        assert payload["retry_after_seconds"] == 2
    finally:
        sender.close()
        receiver.close()
