import datetime
import string
from types import SimpleNamespace

from flask import session

import runserver
from utils import id_generator, check_older_than, process_chat


def test_id_generator_uses_expected_charset_and_length():
    token = id_generator()
    allowed = set(string.ascii_uppercase + string.digits + string.ascii_lowercase)
    assert len(token) == 6
    assert set(token) <= allowed


def test_check_older_than_detects_stale_entry():
    chat = {"timestamp": datetime.datetime.now() - datetime.timedelta(seconds=200)}
    assert check_older_than(chat) is True


def test_check_older_than_keeps_recent_entry():
    chat = {"timestamp": datetime.datetime.now() - datetime.timedelta(seconds=30)}
    assert check_older_than(chat) is False


def test_process_chat_wraps_long_messages(monkeypatch):
    long_message = "message " * 20  # > 69 chars to trigger wrapping
    with runserver.app.test_request_context("/"):
        session["_id"] = "tester"
        session["color"] = (10, 20, 30)
        chat = {
            "msg": long_message,
            "timestamp": datetime.datetime.now(),
            "username": session["_id"],
            "color": session["color"],
        }
        chats = process_chat(chat)

    assert len(chats) > 1
    assert all(len(chunk["msg"]) <= 69 for chunk in chats)
    assert {chunk["username"] for chunk in chats} == {"tester"}


def test_process_chat_preserves_pgp_blocks():
    pgp_message = "-----BEGIN PGP MESSAGE-----\nabc\n-----END PGP MESSAGE-----"
    with runserver.app.test_request_context("/"):
        session["_id"] = "pgp"
        session["color"] = (1, 2, 3)
        chat = {
            "msg": pgp_message,
            "timestamp": datetime.datetime.now(),
            "username": session["_id"],
            "color": session["color"],
        }
        chats = process_chat(chat)

    assert len(chats) == 1
    assert chats[0]["msg"] == pgp_message
    assert chats[0]["username"] == "pgp"


def test_setup_tor_configuration_retries_transient_startup_errors(monkeypatch):
    attempts = {"count": 0}
    sleeps = []

    class FakeController:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def authenticate(self):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("control_auth_cookie missing")

        def create_ephemeral_hidden_service(self, ports, await_publication):
            assert ports == {80: 5000}
            assert await_publication is True
            return SimpleNamespace(service_id="example-service")

    class FakeControllerFactory:
        @staticmethod
        def from_port(address, port):
            assert address == "127.0.0.1"
            assert port == 9051
            return FakeController()

    monkeypatch.setattr(runserver, "Controller", FakeControllerFactory)
    monkeypatch.setattr(runserver, "resolve_tor_control_endpoint", lambda: ("127.0.0.1", 9051))
    monkeypatch.setattr(runserver.time, "sleep", sleeps.append)
    monkeypatch.setattr(runserver.os, "environ", {
        "OPSECHAT_TOR_STARTUP_TIMEOUT": "5",
        "OPSECHAT_TOR_RETRY_DELAY": "0.2",
    })

    hostname, service_id = runserver.setup_tor_configuration()

    assert hostname == "example-service.onion"
    assert service_id == "example-service"
    assert attempts["count"] == 3
    assert sleeps == [0.2, 0.2]
