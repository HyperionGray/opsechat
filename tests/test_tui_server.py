import datetime

from src.tui.server import ChatServer


def make_server() -> ChatServer:
    server = ChatServer()
    # Tests call server methods directly, so disable strict rate limit unless needed.
    server.MAX_MESSAGES_PER_WINDOW = 10_000
    return server


def test_add_message_success():
    server = make_server()
    try:
        success, error = server.add_message("Tester", "hello world")
        assert success is True
        assert error is None
        assert len(server.messages) == 1
        assert server.messages[0]["message"] == "hello world"
    finally:
        server.stop()


def test_rate_limit_rejects_flooding():
    server = ChatServer()
    try:
        username = "RateLimitUser"

        # Fill allowed window
        for i in range(server.MAX_MESSAGES_PER_WINDOW):
            success, error = server.add_message(username, f"m{i}")
            assert success is True
            assert error is None

        # Next message should be rejected
        success, error = server.add_message(username, "overflow")
        assert success is False
        assert error is not None
        assert "Rate limit" in error

        # Move timestamps out of the window and verify sending works again
        with server.lock:
            server.user_message_times[username] = [
                datetime.datetime.now()
                - datetime.timedelta(seconds=server.RATE_LIMIT_WINDOW_SECONDS + 1)
            ]

        success, error = server.add_message(username, "after-window")
        assert success is True
        assert error is None
    finally:
        server.stop()


def test_history_is_capped_server_side():
    server = make_server()
    server.MAX_HISTORY_MESSAGES = 5
    try:
        for i in range(8):
            success, error = server.add_message("HistoryUser", f"msg-{i}")
            assert success is True
            assert error is None

        assert len(server.messages) == 5
        assert server.messages[0]["message"] == "msg-3"
        assert server.messages[-1]["message"] == "msg-7"
    finally:
        server.stop()


def test_cleanup_overwrites_and_deletes_expired_messages():
    server = make_server()
    try:
        success, error = server.add_message("BurnUser", "secret")
        assert success is True
        assert error is None

        msg_ref = server.messages[0]
        msg_ref["timestamp"] = datetime.datetime.now() - datetime.timedelta(
            seconds=server.MESSAGE_LIFETIME + 1
        )

        server._cleanup_old_messages()

        assert len(server.messages) == 0
        assert msg_ref["message"] == "X" * len("secret")
        assert msg_ref["username"].startswith("X")
    finally:
        server.stop()
