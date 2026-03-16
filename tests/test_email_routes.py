"""
Integration-style tests for email_routes registration and behavior.
"""

from urllib.parse import quote

import pytest
from flask import Flask

from domain_manager import domain_rotation_manager
from email_routes import register_email_routes
from email_system import burner_manager, email_storage
from email_transport import transport_manager


def _reset_global_email_state():
    email_storage.emails.clear()
    email_storage.user_keys.clear()

    burner_manager.burner_addresses.clear()
    burner_manager.user_burners.clear()
    burner_manager.send_limits.clear()
    burner_manager.custom_domain = None

    transport_manager.smtp_transport = None
    transport_manager.imap_transport = None

    domain_rotation_manager.api_client = None
    domain_rotation_manager.monthly_budget = 50.0
    domain_rotation_manager.current_spending = 0.0
    domain_rotation_manager.owned_domains = []
    domain_rotation_manager.active_domain = None


@pytest.fixture
def app():
    _reset_global_email_state()

    test_app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    test_app.secret_key = "test-secret"
    test_app.config["TESTING"] = True
    test_app.config["path"] = "test-path-12345"
    test_app.config["hostname"] = "localhost"

    register_email_routes(
        test_app,
        id_generator=lambda size=32: "u" * size,
        get_random_color=lambda: [0, 255, 0],
    )

    yield test_app
    _reset_global_email_state()


@pytest.fixture
def client(app):
    return app.test_client()


def _session_user_id(client):
    with client.session_transaction() as sess:
        return sess["_id"]


def test_email_config_page_renders(client):
    response = client.get("/test-path-12345/email/config")
    assert response.status_code == 200
    assert b"Email System Configuration" in response.data
    assert b"Not Configured" in response.data


def test_compose_local_only_saves_email(client):
    response = client.post(
        "/test-path-12345/email/compose",
        data={
            "raw_mode": "false",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Hello",
            "body": "Test body",
        },
    )

    assert response.status_code == 200
    assert b"Email saved to your local inbox." in response.data

    user_id = _session_user_id(client)
    emails = email_storage.get_emails(user_id)
    assert len(emails) == 1
    assert emails[0]["to"] == "recipient@example.com"
    assert emails[0]["sent"] is True


def test_compose_smtp_requested_without_configuration_fails(client):
    response = client.post(
        "/test-path-12345/email/compose",
        data={
            "raw_mode": "false",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": "Hello",
            "body": "Test body",
            "send_via_smtp": "true",
        },
    )

    assert response.status_code == 200
    assert b"SMTP is not configured" in response.data

    user_id = _session_user_id(client)
    assert email_storage.get_emails(user_id) == []


def test_compose_raw_mode_parses_headers(client):
    raw_email = (
        "From: rawsender@example.com\n"
        "To: rawrecipient@example.com\n"
        "Subject: Raw Subject\n"
        "X-Testing: enabled\n"
        "\n"
        "Raw body"
    )

    response = client.post(
        "/test-path-12345/email/compose",
        data={
            "raw_mode": "true",
            "raw_email": raw_email,
        },
    )

    assert response.status_code == 200
    assert b"Email saved to your local inbox." in response.data

    user_id = _session_user_id(client)
    emails = email_storage.get_emails(user_id)
    assert len(emails) == 1
    assert emails[0]["raw_mode"] is True
    assert emails[0]["headers"]["X-Testing"] == "enabled"


def test_burner_generate_list_and_expire(client):
    generate_response = client.post(
        "/test-path-12345/email/burner",
        data={"action": "generate"},
    )
    assert generate_response.status_code == 200

    list_response = client.get("/test-path-12345/email/burner/list")
    assert list_response.status_code == 200
    burners = list_response.get_json()
    assert isinstance(burners, list)
    assert len(burners) == 1

    burner_email = burners[0]["email"]
    expire_url = f"/test-path-12345/email/burner/expire/{quote(burner_email, safe='')}"
    expire_response = client.post(expire_url)
    assert expire_response.status_code == 302

    post_expire = client.get("/test-path-12345/email/burner/list")
    assert post_expire.status_code == 200
    assert post_expire.get_json() == []


def test_burner_list_json_includes_stats(client):
    client.post("/test-path-12345/email/burner", data={"action": "generate"})
    response = client.get("/test-path-12345/email/burner/list.json")

    assert response.status_code == 200
    payload = response.get_json()
    assert "burners" in payload
    assert "stats" in payload
    assert payload["stats"]["active_burners"] == 1


def test_email_receive_without_imap_redirects_to_config(client):
    response = client.post(
        "/test-path-12345/email/receive",
        data={"limit": "10", "unread_only": "false"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"IMAP is not configured yet." in response.data
