import datetime
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tui.server import ChatServer


def test_default_message_lifetime_is_240_seconds():
    server = ChatServer()
    assert server.MESSAGE_LIFETIME == 240


@pytest.mark.parametrize("bad_value", [0, -1, "abc", None])
def test_rejects_invalid_message_lifetime(bad_value):
    with pytest.raises(ValueError):
        ChatServer(message_lifetime=bad_value)


@pytest.mark.parametrize("bad_value", [0, -5, "oops", None])
def test_rejects_invalid_cleanup_interval(bad_value):
    with pytest.raises(ValueError):
        ChatServer(cleanup_interval_seconds=bad_value)


def test_cleanup_respects_custom_lifetime():
    server = ChatServer(message_lifetime=30, cleanup_interval_seconds=1)
    server.add_message("alice", "keep me")
    server.add_message("bob", "drop me")

    with server.lock:
        server.messages[0]["timestamp"] = datetime.datetime.now() - datetime.timedelta(seconds=20)
        server.messages[1]["timestamp"] = datetime.datetime.now() - datetime.timedelta(seconds=45)
        expired_ref = server.messages[1]

    server._cleanup_old_messages()
    remaining = server.get_messages()

    assert len(remaining) == 1
    assert remaining[0]["message"] == "keep me"
    assert expired_ref["message"] == "X" * len("drop me")
    assert expired_ref["username"] == "X" * len("bob")


def test_lifetime_text_formatting():
    minute_server = ChatServer(message_lifetime=240)
    assert minute_server._format_lifetime_text() == "4 minutes"

    second_server = ChatServer(message_lifetime=75)
    assert second_server._format_lifetime_text() == "75 seconds"
