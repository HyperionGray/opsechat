"""
Focused tests for email route domain rotation integration.
"""

from pathlib import Path

from flask import Flask

from email_routes import register_email_routes


def _create_test_app():
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"))
    app.secret_key = "test-secret-key"
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    register_email_routes(app, lambda: "session-id", lambda: "green")
    return app


def test_email_domain_rotate_json_updates_burner_domain(monkeypatch):
    """Domain rotation endpoint should return JSON and update burner manager."""
    app = _create_test_app()
    client = app.test_client()

    monkeypatch.setattr(
        "email_routes.domain_rotation_manager.rotate_domain",
        lambda: "newdomain.xyz",
    )
    monkeypatch.setattr(
        "email_routes.domain_rotation_manager.get_budget_status",
        lambda: {"remaining": 10.0},
    )
    captured = {"domain": None}

    def _set_custom_domain(domain):
        captured["domain"] = domain

    monkeypatch.setattr("email_routes.burner_manager.set_custom_domain", _set_custom_domain)

    with client.session_transaction() as session_state:
        session_state["_id"] = "session-id"

    response = client.post(
        "/test-path/email/domain/rotate",
        json={},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert response.get_json()["domain"] == "newdomain.xyz"
    assert captured["domain"] == "newdomain.xyz"


def test_email_config_domain_action_stores_status_message(monkeypatch):
    """Domain config action should validate and store success message in session."""
    app = _create_test_app()
    client = app.test_client()

    captured = {}

    def _configure(api_key, secret_key, monthly_budget):
        captured["api_key"] = api_key
        captured["secret_key"] = secret_key
        captured["monthly_budget"] = monthly_budget
        return True

    monkeypatch.setattr("email_routes.domain_rotation_manager.configure", _configure)

    with client.session_transaction() as session_state:
        session_state["_id"] = "session-id"

    response = client.post(
        "/test-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_test_123",
            "api_secret": "sk_test_456",
            "monthly_budget": "25.0",
        },
    )

    assert response.status_code == 302
    assert captured == {
        "api_key": "pk_test_123",
        "secret_key": "sk_test_456",
        "monthly_budget": 25.0,
    }
    with client.session_transaction() as session_state:
        assert session_state["email_config_message"]["type"] == "success"
