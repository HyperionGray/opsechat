"""
Tests for email config route integrations.
"""
from flask import Flask

import email_routes
from email_routes import register_email_routes


def _create_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["path"] = "test-path-12345"
    app.config["hostname"] = "example.onion"
    register_email_routes(app, lambda: "user-id-1", lambda: "green")
    return app


def test_email_config_domain_configuration_action(monkeypatch):
    """Domain API form action should call manager.configure and render success."""
    app = _create_test_app()
    called = {}

    def _fake_configure(api_key, secret_key, monthly_budget=None):
        called["api_key"] = api_key
        called["secret_key"] = secret_key
        called["monthly_budget"] = monthly_budget

    monkeypatch.setattr(email_routes.domain_rotation_manager, "configure", _fake_configure)
    monkeypatch.setattr(email_routes.transport_manager, "is_configured", lambda: {"smtp": False, "imap": False})
    monkeypatch.setattr(email_routes.domain_rotation_manager, "get_budget_status", lambda: {
        "monthly_budget": 50.0,
        "current_spending": 0.0,
        "remaining": 50.0,
        "domains_owned": 0
    })
    monkeypatch.setattr(email_routes.domain_rotation_manager, "get_active_domain", lambda: None)

    client = app.test_client()
    response = client.post(
        "/test-path-12345/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_test",
            "api_secret": "sk_test",
            "monthly_budget": "42.5"
        }
    )

    assert response.status_code == 200
    assert b"Domain API configuration saved" in response.data
    assert called == {
        "api_key": "pk_test",
        "secret_key": "sk_test",
        "monthly_budget": 42.5
    }


def test_email_domain_rotate_redirects_with_message(monkeypatch):
    """Domain rotation endpoint should redirect and persist a success message."""
    app = _create_test_app()
    set_domain = {}

    monkeypatch.setattr(email_routes.domain_rotation_manager, "rotate_domain", lambda: "newburner.xyz")
    monkeypatch.setattr(email_routes.burner_manager, "set_custom_domain", lambda domain: set_domain.setdefault("domain", domain))
    monkeypatch.setattr(email_routes.transport_manager, "is_configured", lambda: {"smtp": False, "imap": False})
    monkeypatch.setattr(email_routes.domain_rotation_manager, "get_budget_status", lambda: {
        "monthly_budget": 50.0,
        "current_spending": 1.0,
        "remaining": 49.0,
        "domains_owned": 1
    })
    monkeypatch.setattr(email_routes.domain_rotation_manager, "get_active_domain", lambda: "newburner.xyz")

    client = app.test_client()
    response = client.post("/test-path-12345/email/domain/rotate", follow_redirects=True)

    assert response.status_code == 200
    assert b"Domain rotated successfully: newburner.xyz" in response.data
    assert set_domain["domain"] == "newburner.xyz"
