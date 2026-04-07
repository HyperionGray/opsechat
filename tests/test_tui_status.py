"""
Tests for TUI status broadcast and client status handling.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer
from src.tui.client import ChatClient


class DummySocket:
    """Simple socket test double capturing sent payloads."""

    def __init__(self):
        self.payloads = []
        self.closed = False

    def send(self, payload):
        self.payloads.append(payload)
        return len(payload)

    def close(self):
        self.closed = True


class TestTuiServerStatus:
    def test_status_snapshot_includes_expected_fields(self):
        server = ChatServer()
        status = server.get_status_snapshot()
        server.cleanup_thread.join(timeout=0.01)

        assert status["type"] == "status"
        assert "user_count" in status
        assert "message_count" in status
        assert status["message_lifetime_seconds"] == server.MESSAGE_LIFETIME

    def test_broadcast_status_sends_to_connected_clients(self):
        server = ChatServer()
        dummy = DummySocket()
        with server.lock:
            server.clients[dummy] = "TestUser0001"

        server.broadcast_status()

        assert len(dummy.payloads) == 1
        payload = dummy.payloads[0].decode("utf-8")
        assert '"type": "status"' in payload
        assert '"user_count": 1' in payload
        server.cleanup_thread.join(timeout=0.01)


class TestTuiClientStatus:
    def test_client_handles_status_message_updates(self):
        client = ChatClient()

        client.handle_server_message(
            {
                "type": "status",
                "user_count": 3,
                "message_count": 8,
                "message_lifetime_seconds": 240,
            }
        )

        assert client.user_count == 3
        assert client.message_count == 8
        assert client.message_lifetime_seconds == 240
        header_text, _ = client.header_text.get_text()
        assert "Users: 3" in header_text
        assert "Messages: 8" in header_text
