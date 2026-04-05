"""
Tests for email route configuration flow.
"""
from unittest.mock import Mock, patch

from app_factory import create_app


def _get_test_path(app):
    app.config["path"] = "test-path-12345"
    app.config["hostname"] = "localhost"
    return app.config["path"]


def test_email_config_get_renders():
    app = create_app()
    app.config["TESTING"] = True
    path = _get_test_path(app)

    with app.test_client() as client:
        response = client.get(f"/{path}/email/config")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Email System Configuration" in body
        assert "Domain API (Porkbun)" in body


def test_email_configure_domain_api_post_sets_success_message():
    app = create_app()
    app.config["TESTING"] = True
    path = _get_test_path(app)

    with app.test_client() as client:
        with patch("email_routes.domain_rotation_manager.configure") as mock_configure:
            mock_configure.return_value = None
            response = client.post(
                f"/{path}/email/config",
                data={
                    "action": "configure_domain_api",
                    "api_key": "pk_test",
                    "api_secret": "sk_test",
                    "monthly_budget": "15.5",
                },
                follow_redirects=True,
            )

        assert response.status_code == 200
        mock_configure.assert_called_once_with(
            api_key="pk_test",
            secret_key="sk_test",
            monthly_budget=15.5,
        )
        body = response.data.decode("utf-8")
        assert "Domain API configuration saved successfully" in body


def test_email_domain_rotate_route_success_redirects_with_message():
    app = create_app()
    app.config["TESTING"] = True
    path = _get_test_path(app)

    with app.test_client() as client:
        with patch("email_routes.domain_rotation_manager.rotate_domain", return_value="newdomain.xyz"):
            response = client.post(
                f"/{path}/email/domain/rotate",
                follow_redirects=True,
            )

        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Domain rotated successfully: newdomain.xyz" in body


def test_email_configure_smtp_action_uses_transport_manager():
    app = create_app()
    app.config["TESTING"] = True
    path = _get_test_path(app)

    with app.test_client() as client:
        with patch("email_routes.transport_manager.configure_smtp", return_value=True) as mock_smtp:
            response = client.post(
                f"/{path}/email/config",
                data={
                    "action": "configure_smtp",
                    "smtp_server": "smtp.example.com",
                    "smtp_port": "587",
                    "smtp_username": "user@example.com",
                    "smtp_password": "secret",
                    "use_tls": "on",
                },
                follow_redirects=True,
            )

        assert response.status_code == 200
        mock_smtp.assert_called_once_with(
            smtp_server="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="secret",
            use_tls=True,
        )
        body = response.data.decode("utf-8")
        assert "SMTP configuration saved successfully" in body
