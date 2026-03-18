"""
Integration tests for email configuration routes.
"""
from app_factory import create_app
import email_routes


def _make_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["path"] = "test-path-123"
    app.config["hostname"] = "localhost"
    return app


def test_email_config_page_renders():
    app = _make_app()
    with app.test_client() as client:
        response = client.get("/test-path-123/email/config")
        assert response.status_code == 200
        assert b"Email System Configuration" in response.data


def test_email_config_domain_action_calls_configure(monkeypatch):
    app = _make_app()
    captured = {}

    def fake_configure(**kwargs):
        captured.update(kwargs)
        return {"configured": True}

    monkeypatch.setattr(email_routes.domain_rotation_manager, "configure", fake_configure)

    with app.test_client() as client:
        response = client.post(
            "/test-path-123/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk_test_1234",
                "api_secret": "sk_test_5678",
                "monthly_budget": "25.5",
            },
        )

        assert response.status_code == 200
        assert captured["api_key"] == "pk_test_1234"
        assert captured["api_secret"] == "sk_test_5678"
        assert captured["monthly_budget"] == 25.5
        assert b"Domain API configuration saved successfully" in response.data


def test_email_domain_rotate_returns_json(monkeypatch):
    app = _make_app()

    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "get_config",
        lambda: {"configured": True},
    )
    monkeypatch.setattr(
        email_routes.domain_rotation_manager,
        "rotate_domain",
        lambda: "rotated-example.xyz",
    )

    with app.test_client() as client:
        response = client.post(
            "/test-path-123/email/domain/rotate",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["active_domain"] == "rotated-example.xyz"


def test_email_receive_returns_json(monkeypatch):
    app = _make_app()

    monkeypatch.setattr(
        email_routes.transport_manager,
        "is_configured",
        lambda: {"smtp": False, "imap": True},
    )
    monkeypatch.setattr(
        email_routes.transport_manager,
        "receive_emails",
        lambda folder, limit, unread_only: [
            {
                "from": "sender@example.com",
                "to": "user@example.com",
                "subject": "hello",
                "body": "test",
                "sent": False,
            }
        ],
    )

    with app.test_client() as client:
        response = client.post(
            "/test-path-123/email/receive",
            data={"limit": "10", "unread_only": "false"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["emails_fetched"] == 1
