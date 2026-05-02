"""
Focused regression tests for HTTP mail routes.

These tests avoid full app_factory wiring and validate the route-level behavior
that recently changed around generic send and inbox-open helpers.
"""

import os

from flask import Flask

from http_mail_routes import register_http_mail_routes
from http_mail_system import http_mail_storage


def _fresh_client():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(repo_root, "templates"))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    register_http_mail_routes(app)
    return app.test_client()


def _clear_http_mail_storage():
    with http_mail_storage._lock:
        http_mail_storage._mailboxes.clear()
        http_mail_storage._aliases.clear()


def setup_function():
    _clear_http_mail_storage()


def teardown_function():
    _clear_http_mail_storage()


def test_generic_send_requires_mailbox_address():
    client = _fresh_client()
    response = client.post(
        "/secpath/mail/send",
        data={"subject": "hello", "body": "world", "sender": "alice"},
    )
    assert response.status_code == 400
    assert b"Recipient mailbox address is required" in response.data


def test_open_inbox_helper_requires_address_and_key():
    client = _fresh_client()
    response = client.get("/secpath/mail/open?address=mailbox-only")
    assert response.status_code == 400
    assert b"Mailbox address and read key are required" in response.data


def test_open_inbox_helper_accepts_fallback_query_keys():
    client = _fresh_client()
    mailbox = http_mail_storage.create_mailbox()

    response = client.get(
        f"/secpath/mail/open?_read_address={mailbox.address}&_read_key={mailbox.read_key}"
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/secpath/mail/{mailbox.address}/inbox?key={mailbox.read_key}"
    )
