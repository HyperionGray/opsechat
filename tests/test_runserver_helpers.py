import datetime
import math
import string
from types import SimpleNamespace

from flask import session
from stem.connection import AuthenticationFailure

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
                raise AuthenticationFailure("control_auth_cookie missing")

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
    monkeypatch.setenv("OPSECHAT_TOR_STARTUP_TIMEOUT", "5")
    monkeypatch.setenv("OPSECHAT_TOR_RETRY_DELAY", "0.2")

    hostname, service_id = runserver.setup_tor_configuration()

    assert hostname == "example-service.onion"
    assert service_id == "example-service"
    assert attempts["count"] == 3
    assert sleeps == [0.2, 0.2]


def test_setup_tor_configuration_requires_service_id_when_tor_required(monkeypatch):
    class FakeController:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def authenticate(self):
            return None

        def create_ephemeral_hidden_service(self, ports, await_publication):
            return SimpleNamespace(service_id=None)

    class FakeControllerFactory:
        @staticmethod
        def from_port(address, port):
            return FakeController()

    monkeypatch.setattr(runserver, "Controller", FakeControllerFactory)
    monkeypatch.setattr(runserver, "resolve_tor_control_endpoint", lambda: ("127.0.0.1", 9051))
    monkeypatch.setattr(runserver, "tor_ingress_required", lambda: True)

    try:
        runserver.setup_tor_configuration()
    except RuntimeError as exc:
        assert "hidden service ID could not be determined" in str(exc)
    else:
        raise AssertionError("Expected setup_tor_configuration to fail when Tor is required")


def test_setup_tor_configuration_returns_localhost_when_service_id_missing_and_tor_optional(monkeypatch):
    class FakeController:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def authenticate(self):
            return None

        def create_ephemeral_hidden_service(self, ports, await_publication):
            return SimpleNamespace(service_id=None)

    class FakeControllerFactory:
        @staticmethod
        def from_port(address, port):
            return FakeController()

    monkeypatch.setattr(runserver, "Controller", FakeControllerFactory)
    monkeypatch.setattr(runserver, "resolve_tor_control_endpoint", lambda: ("127.0.0.1", 9051))
    monkeypatch.setattr(runserver, "tor_ingress_required", lambda: False)

    hostname, service_id = runserver.setup_tor_configuration()

    assert hostname == "localhost"
    assert service_id is None


def test_setup_tor_configuration_fails_fast_on_invalid_control_endpoint_when_tor_required(monkeypatch):
    monkeypatch.setattr(runserver, "resolve_tor_control_endpoint", lambda: (_ for _ in ()).throw(ValueError("bad port")))
    monkeypatch.setattr(runserver, "tor_ingress_required", lambda: True)

    try:
        runserver.setup_tor_configuration()
    except RuntimeError as exc:
        assert "hidden service could not be created" in str(exc)
        assert isinstance(exc.__cause__, ValueError)
    else:
        raise AssertionError("Expected setup_tor_configuration to fail when Tor is required")


def test_get_positive_float_env_rejects_non_finite_values(monkeypatch):
    monkeypatch.setenv("OPSECHAT_TOR_STARTUP_TIMEOUT", "nan")

    try:
        runserver._get_positive_float_env("OPSECHAT_TOR_STARTUP_TIMEOUT", 30, 1.0)
    except RuntimeError as exc:
        assert "must be finite" in str(exc)
    else:
        raise AssertionError("Expected non-finite float values to be rejected")
