"""
Integration tests for email configuration routes.
"""
from unittest.mock import patch

from app_factory import create_app
from domain_manager import domain_rotation_manager
from email_transport import transport_manager


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    return app


def _reset_global_managers():
    transport_manager.smtp_transport = None
    transport_manager.imap_transport = None
    domain_rotation_manager.api_client = None
    domain_rotation_manager._api_key = None
    domain_rotation_manager._api_secret = None
    domain_rotation_manager.monthly_budget = 50.0
    domain_rotation_manager.current_spending = 0.0
    domain_rotation_manager.owned_domains = []
    domain_rotation_manager.active_domain = None


class TestEmailConfigRoutes:
    def setup_method(self):
        _reset_global_managers()
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def test_email_config_get_renders(self):
        resp = self.client.get("/secpath/email/config")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True).lower()
        assert "email system configuration" in body
        assert "smtp" in body
        assert "imap" in body

    @patch("email_routes.transport_manager.configure_smtp", return_value=True)
    def test_email_config_post_configure_smtp(self, mock_configure):
        resp = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_smtp",
                "smtp_server": "smtp.example.com",
                "smtp_port": "587",
                "smtp_username": "user@example.com",
                "smtp_password": "secret",
                "use_tls": "on",
            },
        )
        assert resp.status_code == 200
        assert mock_configure.called
        assert "smtp configuration saved".lower() in resp.get_data(as_text=True).lower()

    @patch("email_routes.transport_manager.receive_emails", return_value=[])
    @patch("email_routes.transport_manager.is_configured", return_value={"smtp": False, "imap": False})
    def test_email_receive_returns_json_error_when_imap_not_configured(
        self, _mock_is_configured, _mock_receive
    ):
        resp = self.client.post("/secpath/email/receive", json={"limit": 5, "unread_only": True})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "imap" in data["error"].lower()

    @patch("email_routes.domain_rotation_manager.rotate_domain", return_value="newdomain.xyz")
    def test_domain_rotate_json_success(self, mock_rotate):
        resp = self.client.post("/secpath/email/domain/rotate", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["domain"] == "newdomain.xyz"
        assert mock_rotate.called
