"""
Integration tests for email_security_routes blueprint configuration flows.
"""

import os
import sys

from flask import Flask

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import email_security_routes as routes_module
from email_security_routes import create_email_security_blueprint


class _StubTransportManager:
    def __init__(self):
        self.smtp_configured = False
        self.imap_configured = False
        self.last_smtp = {}
        self.last_imap = {}

    def is_configured(self):
        return {"smtp": self.smtp_configured, "imap": self.imap_configured}

    def configure_smtp(self, smtp_server, smtp_port, username, password, use_tls=True):
        self.last_smtp = {
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "use_tls": use_tls,
        }
        self.smtp_configured = True
        return True

    def configure_imap(self, imap_server, imap_port, username, password, use_ssl=True):
        self.last_imap = {
            "imap_server": imap_server,
            "imap_port": imap_port,
            "username": username,
            "password": password,
            "use_ssl": use_ssl,
        }
        self.imap_configured = True
        return True

    def receive_emails(self, limit=None, unread_only=False):
        return []


class _StubDomainManager:
    def __init__(self):
        self.configured = False
        self.last_config = {}
        self.active_domain = None
        self.monthly_budget = 50.0
        self.current_spending = 0.0
        self.owned_domains = []

    def configure(self, api_key, secret_key, monthly_budget=50.0):
        self.configured = True
        self.last_config = {
            "api_key": api_key,
            "secret_key": secret_key,
            "monthly_budget": monthly_budget,
        }
        self.monthly_budget = monthly_budget
        return {"success": True}

    def get_config(self):
        api_key = self.last_config.get("api_key", "")
        masked = f"{'*' * max(0, len(api_key) - 4)}{api_key[-4:]}" if api_key else None
        return {
            "configured": self.configured,
            "api_key_masked": masked,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def get_budget_status(self):
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
        }

    def get_active_domain(self):
        return self.active_domain

    def rotate_domain_with_result(self, max_price=5.0):
        self.active_domain = "rotated-example.xyz"
        self.current_spending += 1.99
        return {"success": True, "domain": self.active_domain, "price": 1.99}


def _build_app(monkeypatch):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, template_folder=os.path.join(project_root, "templates"))
    app.secret_key = "test-secret"
    app.config["path"] = "secret-path"
    app.config["hostname"] = "example.onion"

    stub_transport = _StubTransportManager()
    stub_domain = _StubDomainManager()
    monkeypatch.setattr(routes_module, "transport_manager", stub_transport)
    monkeypatch.setattr(routes_module, "domain_rotation_manager", stub_domain)

    bp = create_email_security_blueprint(lambda: "session-id", lambda: "green")
    app.register_blueprint(bp)
    return app, stub_transport, stub_domain


def test_email_config_accepts_domain_form_action(monkeypatch):
    app, _, stub_domain = _build_app(monkeypatch)
    client = app.test_client()

    response = client.post(
        "/secret-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_test_1234",
            "api_secret": "sk_test_5678",
            "monthly_budget": "42.50",
        },
    )

    assert response.status_code == 200
    assert stub_domain.configured is True
    assert stub_domain.last_config["api_key"] == "pk_test_1234"
    assert stub_domain.last_config["monthly_budget"] == 42.5
    assert b"Domain configuration saved successfully" in response.data


def test_email_config_maps_smtp_field_names(monkeypatch):
    app, stub_transport, _ = _build_app(monkeypatch)
    client = app.test_client()

    response = client.post(
        "/secret-path/email/config",
        data={
            "action": "configure_smtp",
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "user@example.com",
            "smtp_password": "pw",
            "use_tls": "true",
        },
    )

    assert response.status_code == 200
    assert stub_transport.smtp_configured is True
    assert stub_transport.last_smtp["username"] == "user@example.com"
    assert stub_transport.last_smtp["use_tls"] is True
    assert b"SMTP configuration saved successfully" in response.data


def test_email_domain_rotate_returns_json_result(monkeypatch):
    app, _, _ = _build_app(monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_id"] = "session-id"

    response = client.post("/secret-path/email/domain/rotate")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["domain"] == "rotated-example.xyz"
