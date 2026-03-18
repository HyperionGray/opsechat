"""
Tests for email configuration and domain rotation routes.
"""
from flask import Flask
from unittest.mock import patch

from email_routes import register_email_routes
from email_system import email_storage, burner_manager
from email_transport import transport_manager
from domain_manager import domain_rotation_manager


def _id_generator(size=8):
    return "test-user-id"


def _color_generator():
    return "green"


def _build_app():
    app = Flask(__name__, template_folder="/workspace/templates")
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    register_email_routes(app, _id_generator, _color_generator)
    return app


def setup_function(_):
    """Reset global state used by route handlers."""
    email_storage.emails.clear()
    burner_manager.burner_addresses.clear()
    domain_rotation_manager.api_client = None
    domain_rotation_manager.current_spending = 0.0
    domain_rotation_manager.owned_domains = []
    domain_rotation_manager.active_domain = None
    domain_rotation_manager._api_key_suffix = None


def test_email_config_get_renders_template_context():
    app = _build_app()
    client = app.test_client()

    response = client.get("/test-path/email/config")

    assert response.status_code == 200
    assert b"Email System Configuration" in response.data
    assert b"Budget Status" in response.data


def test_email_config_domain_configuration_post():
    app = _build_app()
    client = app.test_client()

    response = client.post(
        "/test-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk1_examplekey",
            "api_secret": "sk1_examplesecret",
            "monthly_budget": "15.50",
        },
    )

    assert response.status_code == 200
    assert b"Domain configuration saved successfully" in response.data
    assert domain_rotation_manager.get_config()["configured"] is True
    assert domain_rotation_manager.monthly_budget == 15.5


def test_email_domain_rotate_and_receive_routes():
    app = _build_app()
    client = app.test_client()

    with patch.object(
        domain_rotation_manager,
        "rotate_domain_with_details",
        return_value={"success": True, "domain": "newburner.xyz", "price": 1.99},
    ), patch.object(burner_manager, "set_custom_domain") as mock_set_domain:
        rotate_response = client.post("/test-path/email/domain/rotate", follow_redirects=False)
        assert rotate_response.status_code == 302
        assert rotate_response.location.endswith("/test-path/email/config")
        mock_set_domain.assert_called_once_with("newburner.xyz")

    sample_emails = [
        {"from": "sender1@test.com", "to": "dest@test.com", "subject": "S1", "body": "B1"},
        {"from": "sender2@test.com", "to": "dest@test.com", "subject": "S2", "body": "B2"},
    ]
    with patch.object(transport_manager, "receive_emails", return_value=sample_emails), patch.object(
        transport_manager, "is_configured", return_value={"smtp": False, "imap": True}
    ):
        receive_response = client.post(
            "/test-path/email/receive",
            data={"limit": "2", "unread_only": "false"},
            follow_redirects=True,
        )
        assert receive_response.status_code == 200
        assert b"Fetched 2 email(s) from IMAP." in receive_response.data

    with client.session_transaction() as sess:
        user_id = sess["_id"]

    inbox = email_storage.get_emails(user_id)
    assert len(inbox) == 2
