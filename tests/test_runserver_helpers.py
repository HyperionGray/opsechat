import datetime
import string
import os

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


def test_get_tor_control_settings_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("TOR_CONTROL_HOST", raising=False)
    monkeypatch.delenv("TOR_CONTROL_PORT", raising=False)

    host, port = runserver._get_tor_control_settings()
    assert host == "127.0.0.1"
    assert port == 9051


def test_get_tor_control_settings_reads_valid_env(monkeypatch):
    monkeypatch.setenv("TOR_CONTROL_HOST", "tor")
    monkeypatch.setenv("TOR_CONTROL_PORT", "19051")

    host, port = runserver._get_tor_control_settings()
    assert host == "tor"
    assert port == 19051


def test_get_tor_control_settings_falls_back_on_invalid_port(monkeypatch):
    monkeypatch.setenv("TOR_CONTROL_HOST", "tor")
    monkeypatch.setenv("TOR_CONTROL_PORT", "invalid-port")

    host, port = runserver._get_tor_control_settings()
    assert host == "tor"
    assert port == 9051
