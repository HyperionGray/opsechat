"""
Integration tests for email domain configuration and rotation routes.
"""
from app_factory import create_app
from domain_manager import domain_rotation_manager
from email_transport import transport_manager


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    return app


def _patch_common_status(monkeypatch, configured=False):
    monkeypatch.setattr(transport_manager, "is_configured", lambda: {"smtp": False, "imap": False})
    monkeypatch.setattr(
        domain_rotation_manager,
        "get_budget_status",
        lambda: {
            "monthly_budget": 50.0,
            "current_spending": 0.0,
            "remaining": 50.0,
            "domains_owned": 0,
        },
    )
    monkeypatch.setattr(domain_rotation_manager, "get_active_domain", lambda: None)
    monkeypatch.setattr(
        domain_rotation_manager,
        "get_config",
        lambda: {
            "configured": configured,
            "registrar": "porkbun" if configured else None,
            "api_key_configured": configured,
            "api_key_suffix": "1234" if configured else None,
            "monthly_budget": 50.0,
            "current_spending": 0.0,
            "active_domain": None,
            "domains_owned": 0,
        },
    )


def test_email_config_domain_action(monkeypatch):
    app = _fresh_app()
    client = app.test_client()
    _patch_common_status(monkeypatch, configured=True)

    captured = {}

    def fake_configure(api_key, secret_key, monthly_budget, registrar="porkbun"):
        captured["api_key"] = api_key
        captured["secret_key"] = secret_key
        captured["monthly_budget"] = monthly_budget
        captured["registrar"] = registrar
        return {"configured": True}

    monkeypatch.setattr(domain_rotation_manager, "configure", fake_configure)

    response = client.post(
        "/test-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk1_test_value",
            "api_secret": "sk1_test_value",
            "monthly_budget": "33.50",
        },
    )

    assert response.status_code == 200
    assert b"Domain API configuration saved successfully." in response.data
    assert captured["api_key"] == "pk1_test_value"
    assert captured["secret_key"] == "sk1_test_value"
    assert captured["monthly_budget"] == 33.5
    assert captured["registrar"] == "porkbun"


def test_email_domain_rotate_redirects_with_success_message(monkeypatch):
    app = _fresh_app()
    client = app.test_client()
    _patch_common_status(monkeypatch, configured=True)
    monkeypatch.setattr(
        domain_rotation_manager,
        "rotate_domain_with_details",
        lambda: {"success": True, "domain": "rotate123.xyz", "price": 2.99},
    )

    response = client.post("/test-path/email/domain/rotate", follow_redirects=True)

    assert response.status_code == 200
    assert b"Domain rotation successful: rotate123.xyz ($2.99)" in response.data


def test_email_domain_rotate_requires_configuration(monkeypatch):
    app = _fresh_app()
    client = app.test_client()
    _patch_common_status(monkeypatch, configured=False)

    response = client.post("/test-path/email/domain/rotate", follow_redirects=True)

    assert response.status_code == 200
    assert b"Configure Domain API credentials before rotating domains." in response.data
