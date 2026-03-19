import json
from unittest.mock import patch

from src.tui.server import ChatServer


class FakeSocket:
    def __init__(self, recv_chunks=None, fail_on_send=False):
        self.recv_chunks = list(recv_chunks or [])
        self.fail_on_send = fail_on_send
        self.sent = []
        self.closed = False

    def send(self, data):
        if self.fail_on_send:
            raise OSError("send failed")
        self.sent.append(data.decode("utf-8"))
        return len(data)

    def recv(self, _bufsize):
        if self.recv_chunks:
            return self.recv_chunks.pop(0)
        return b""

    def close(self):
        self.closed = True


def _decode_sent_messages(fake_socket):
    messages = []
    for chunk in fake_socket.sent:
        for line in chunk.splitlines():
            if line.strip():
                messages.append(json.loads(line))
    return messages


def test_presence_and_system_events_on_join_and_leave():
    server = ChatServer()
    server.running = True
    observer = FakeSocket()
    incoming = FakeSocket(recv_chunks=[b""])

    try:
        with server.lock:
            server.clients[observer] = "ExistingUser0001"

        with patch.object(server, "generate_username", return_value="NewUser0002"):
            server.handle_client(incoming, ("127.0.0.1", 5000))

        observer_events = _decode_sent_messages(observer)
        incoming_events = _decode_sent_messages(incoming)

        welcome_events = [m for m in incoming_events if m.get("type") == "welcome"]
        assert welcome_events, "new user should receive welcome"
        assert welcome_events[0]["online"] == 2

        assert any(
            m.get("type") == "system" and "joined the room" in m.get("message", "")
            for m in observer_events
        )
        assert any(m.get("type") == "presence" and m.get("online") == 2 for m in observer_events)
        assert any(
            m.get("type") == "system" and "left the room" in m.get("message", "")
            for m in observer_events
        )
        assert any(m.get("type") == "presence" and m.get("online") == 1 for m in observer_events)
    finally:
        server.stop()


def test_malformed_json_sends_protocol_error():
    server = ChatServer()
    server.running = True
    incoming = FakeSocket(recv_chunks=[b"{bad-json}\n", b""])

    try:
        with patch.object(server, "generate_username", return_value="BadSender0001"):
            server.handle_client(incoming, ("127.0.0.1", 5001))

        events = _decode_sent_messages(incoming)
        assert any(
            m.get("type") == "error" and "Malformed JSON payload" in m.get("message", "")
            for m in events
        )
    finally:
        server.stop()
