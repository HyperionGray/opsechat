import datetime

from src.tui.server import ChatServer


class DummySocket:
    def __init__(self):
        self.sent_payloads = []
        self.closed = False

    def send(self, data):
        self.sent_payloads.append(data.decode("utf-8"))
        return len(data)

    def close(self):
        self.closed = True


def test_room_name_validation_and_join():
    server = ChatServer()
    client = object()

    assert server.normalize_room_name(" Ops_Room-1 ") == "ops_room-1"
    assert server.normalize_room_name("bad room!") is None
    assert server.normalize_room_name("") is None

    assert server.join_room(client, "intel") == {"old_room": "lobby", "new_room": "intel"}
    assert server.get_client_room(client) == "intel"
    assert server.join_room(client, "intel") == {"old_room": "intel", "new_room": "intel"}

    server.stop()


def test_messages_are_room_scoped():
    server = ChatServer()

    assert server.add_message("alice", "hello lobby", room="lobby")
    assert server.add_message("bob", "hello red", room="red")
    assert server.add_message("carol", "hello blue", room="blue")

    lobby_messages = server.get_messages(room="lobby")
    red_messages = server.get_messages(room="red")
    blue_messages = server.get_messages(room="blue")

    assert [m["message"] for m in lobby_messages] == ["hello lobby"]
    assert [m["message"] for m in red_messages] == ["hello red"]
    assert [m["message"] for m in blue_messages] == ["hello blue"]

    since = datetime.datetime.now() + datetime.timedelta(seconds=1)
    assert server.get_messages(since=since, room="lobby") == []

    server.stop()


def test_broadcast_only_reaches_same_room_clients():
    server = ChatServer()
    alpha_client = DummySocket()
    beta_client = DummySocket()

    with server.lock:
        server.clients[alpha_client] = "alpha-user"
        server.clients[beta_client] = "beta-user"
        server.client_rooms[alpha_client] = "alpha"
        server.client_rooms[beta_client] = "beta"

    server.broadcast_message("alpha-user", "alpha-msg", room="alpha")
    server.broadcast_message("beta-user", "beta-msg", room="beta")

    assert any('"room": "alpha"' in payload for payload in alpha_client.sent_payloads)
    assert not any('"room": "beta"' in payload for payload in alpha_client.sent_payloads)
    assert any('"room": "beta"' in payload for payload in beta_client.sent_payloads)
    assert not any('"room": "alpha"' in payload for payload in beta_client.sent_payloads)

    server.stop()
