"""
Focused regression tests for HTTP mail routes.

These tests avoid full app_factory wiring and validate the route-level behavior
that recently changed around generic send and inbox-open helpers.
"""

import os

from flask import Flask

import http_mail_routes
from http_mail_routes import register_http_mail_routes
from http_mail_system import http_mail_storage


def _fresh_client():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(repo_root, "src", "web", "templates"),
    )
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
        data={"ciphertext": '{"version":"shared-secret-v1"}'},
    )
    assert response.status_code == 400
    assert b"Recipient mailbox address is required" in response.data


def test_open_inbox_helper_requires_address():
    client = _fresh_client()
    response = client.get("/secpath/mail/open")
    assert response.status_code == 400
    assert b"Inbox username is required" in response.data


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


def test_open_inbox_helper_preserves_read_key():
    client = _fresh_client()
    mailbox = http_mail_storage.create_mailbox()

    response = client.get(
        f"/secpath/mail/open?address={mailbox.address}&key={mailbox.read_key}"
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/secpath/mail/{mailbox.address}/inbox?key={mailbox.read_key}"
    )


def test_server_rendered_inbox_forms_include_read_key():
    client = _fresh_client()
    mailbox = http_mail_storage.create_mailbox()
    msg_id = mailbox.add_encrypted_message('{"version":"shared-secret-v1"}')

    response = client.get(
        f"/secpath/mail/{mailbox.address}/inbox?key={mailbox.read_key}"
    )

    assert response.status_code == 200
    assert f'value="{mailbox.read_key}"'.encode() in response.data

    delete_response = client.post(
        f"/secpath/mail/{mailbox.address}/delete/{msg_id}",
        data={"read_key": mailbox.read_key},
    )
    assert delete_response.status_code == 302

    destroy_response = client.post(
        f"/secpath/mail/{mailbox.address}/destroy",
        data={"read_key": mailbox.read_key},
    )
    assert destroy_response.status_code == 200
    assert b"Mailbox destroyed." in destroy_response.data


def test_create_mailbox_retries_alias_collision(monkeypatch):
    client = _fresh_client()
    calls = {"count": 0}

    def fake_generate_mailbox_alias():
        calls["count"] += 1
        return "race-alias" if calls["count"] == 1 else "safe-alias"

    real_create_mailbox = http_mail_storage.create_mailbox

    def fake_create_mailbox(*args, **kwargs):
        if kwargs.get("alias") == "race-alias":
            raise ValueError("Mailbox alias already exists")
        return real_create_mailbox(*args, **kwargs)

    monkeypatch.setattr(
        http_mail_routes,
        "generate_mailbox_alias",
        fake_generate_mailbox_alias,
    )
    monkeypatch.setattr(
        http_mail_storage,
        "create_mailbox",
        fake_create_mailbox,
    )

    response = client.post("/secpath/mail/new")

    assert response.status_code == 200
    assert response.get_json()["address"] == "safe-alias"
