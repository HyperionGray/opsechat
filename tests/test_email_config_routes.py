"""
Tests for email configuration routes and actions.
"""
import os
import sys

from flask import Flask

# Ensure project root can be imported in CI/local execution.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_routes import register_email_routes, transport_manager, domain_rotation_manager  # noqa: E402


def _build_test_app():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(project_root, "templates"))
    app.secret_key = "test-secret-key"
    app.config["path"] = "unit-path"
    app.config["hostname"] = "localhost"

    def _id_generator(size=16):
        return "test-session-id"

    def _random_color():
        return "green"

    register_email_routes(app, _id_generator, _random_color)
    return app


def test_email_config_get_renders_dashboard():
    app = _build_test_app()
    client = app.test_client()

    response = client.get("/unit-path/email/config")
    assert response.status_code == 200
    assert b"Email System Configuration" in response.data


def test_email_config_post_configure_smtp(monkeypatch):
    app = _build_test_app()
    client = app.test_client()

    client.get("/unit-path/email/config")
    monkeypatch.setattr(transport_manager, "configure_smtp", lambda **kwargs: True)

    response = client.post(
        "/unit-path/email/config",
        data={
            "action": "configure_smtp",
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "user@example.com",
            "smtp_password": "password",
            "use_tls": "true",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"SMTP configuration saved and connection test passed." in response.data


def test_email_config_post_configure_domain_api(monkeypatch):
    app = _build_test_app()
    client = app.test_client()

    client.get("/unit-path/email/config")

    captured = {}

    def _configure(api_key, secret_key, monthly_budget):
        captured["api_key"] = api_key
        captured["secret_key"] = secret_key
        captured["monthly_budget"] = monthly_budget
        return True

    monkeypatch.setattr(domain_rotation_manager, "configure", _configure)

    response = client.post(
        "/unit-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_example",
            "api_secret": "sk_example",
            "monthly_budget": "75.50",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured == {
        "api_key": "pk_example",
        "secret_key": "sk_example",
        "monthly_budget": 75.5,
    }
    assert b"Domain API configuration updated." in response.data


def test_email_domain_rotate_endpoint_redirects_with_message(monkeypatch):
    app = _build_test_app()
    client = app.test_client()

    client.get("/unit-path/email/config")
    monkeypatch.setattr(domain_rotation_manager, "rotate_domain", lambda: "newdomain.xyz")

    response = client.post("/unit-path/email/domain/rotate", follow_redirects=True)
    assert response.status_code == 200
    assert b"Domain rotated successfully to newdomain.xyz." in response.data


def test_email_receive_fetches_and_reports_count(monkeypatch):
    app = _build_test_app()
    client = app.test_client()

    client.get("/unit-path/email/config")
    monkeypatch.setattr(transport_manager, "is_configured", lambda: {"smtp": False, "imap": True})
    monkeypatch.setattr(
        transport_manager,
        "receive_emails",
        lambda limit=None, unread_only=False: [{"from": "a@test.com", "to": "b@test.com", "subject": "s", "body": "b"}],
    )

    response = client.post(
        "/unit-path/email/receive",
        data={"limit": "10", "unread_only": "true"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Fetched 1 emails from IMAP." in response.data
