"""
Tests for email configuration and domain rotation routes.
"""

from app_factory import create_app
from domain_manager import domain_rotation_manager
from email_system import burner_manager


def _make_test_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    return app.test_client()


def test_email_config_page_renders():
    client = _make_test_client()
    response = client.get("/test-path/email/config")

    assert response.status_code == 200
    assert b"Email System Configuration" in response.data


def test_email_config_domain_post_shows_success(monkeypatch):
    client = _make_test_client()

    called = {}

    def fake_configure(api_key, secret_key, monthly_budget):
        called["api_key"] = api_key
        called["secret_key"] = secret_key
        called["monthly_budget"] = monthly_budget

    monkeypatch.setattr(domain_rotation_manager, "configure", fake_configure)

    response = client.post(
        "/test-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_test",
            "api_secret": "sk_test",
            "monthly_budget": "25.0",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Domain API configuration saved successfully" in response.data
    assert called["api_key"] == "pk_test"
    assert called["secret_key"] == "sk_test"
    assert called["monthly_budget"] == 25.0


def test_email_domain_rotate_updates_burner_domain(monkeypatch):
    client = _make_test_client()

    monkeypatch.setattr(
        domain_rotation_manager,
        "rotate_domain_with_result",
        lambda: {
            "success": True,
            "domain": "newburner.xyz",
            "price": 1.99,
            "budget": {"domains_owned": 1},
        },
    )

    updated = {}

    def fake_set_custom_domain(domain):
        updated["domain"] = domain

    monkeypatch.setattr(burner_manager, "set_custom_domain", fake_set_custom_domain)

    response = client.post("/test-path/email/domain/rotate", follow_redirects=True)

    assert response.status_code == 200
    assert b"Domain rotated successfully to newburner.xyz." in response.data
    assert updated["domain"] == "newburner.xyz"
