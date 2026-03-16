"""
Integration tests for email configuration and domain rotation routes.
"""

import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
import email_routes


def _make_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["hostname"] = "localhost"
    app.config["path"] = "test-path"
    return app


def _stub_domain_status(monkeypatch):
    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "get_config",
        lambda: {
            "configured": False,
            "provider": "none",
            "monthly_budget": 50.0,
            "current_spending": 0.0,
            "active_domain": None,
            "domains_owned": 0,
        },
    )
    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "get_budget_status",
        lambda: {
            "monthly_budget": 50.0,
            "current_spending": 0.0,
            "remaining": 50.0,
            "domains_owned": 0,
        },
    )
    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "get_active_domain",
        lambda: None,
    )


def test_email_config_page_renders(monkeypatch):
    app = _make_app()
    _stub_domain_status(monkeypatch)
    monkeypatch.setattr(email_routes.transport_manager, "is_configured", lambda: {"smtp": False, "imap": False})

    with app.test_client() as client:
        response = client.get("/test-path/email/config")

    assert response.status_code == 200
    assert b"Email System Configuration" in response.data
    assert b"Domain API (Porkbun)" in response.data


def test_email_config_domain_submit_redirects_with_success(monkeypatch):
    app = _make_app()
    _stub_domain_status(monkeypatch)
    monkeypatch.setattr(email_routes.transport_manager, "is_configured", lambda: {"smtp": False, "imap": False})

    captured = {}

    def _configure(api_key, secret_key, monthly_budget):
        captured["api_key"] = api_key
        captured["secret_key"] = secret_key
        captured["monthly_budget"] = monthly_budget
        return {"configured": True}

    monkeypatch.setattr(email_routes.domain_rotation_manager, "configure", _configure)

    with app.test_client() as client:
        response = client.post(
            "/test-path/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk1_test_key",
                "api_secret": "sk1_test_secret",
                "monthly_budget": "20",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert captured == {
        "api_key": "pk1_test_key",
        "secret_key": "sk1_test_secret",
        "monthly_budget": 20.0,
    }
    assert b"Domain API configuration saved in memory." in response.data


def test_email_domain_rotate_returns_json(monkeypatch):
    app = _make_app()
    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "rotate_domain_with_details",
        lambda: {
            "success": True,
            "domain": "abc123.xyz",
            "price": 2.99,
            "remaining_budget": 47.01,
        },
    )

    with app.test_client() as client:
        response = client.post(
            "/test-path/email/domain/rotate",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["domain"] == "abc123.xyz"
