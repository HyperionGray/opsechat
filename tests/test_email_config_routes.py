"""
Tests for email configuration route integration.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from domain_manager import domain_rotation_manager


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    return app


class TestEmailConfigRoutes:
    def setup_method(self):
        self.app = _fresh_app()
        self.client = self.app.test_client()
        # Reset singleton manager state to avoid test bleed.
        domain_rotation_manager.api_client = None
        domain_rotation_manager._api_key = None
        domain_rotation_manager._secret_key = None
        domain_rotation_manager.monthly_budget = 50.0
        domain_rotation_manager.current_spending = 0.0
        domain_rotation_manager.owned_domains = []
        domain_rotation_manager.active_domain = None

    def test_email_config_page_renders(self):
        resp = self.client.get("/test-path/email/config")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8").lower()
        assert "email system configuration" in body
        assert "domain api" in body

    @patch("email_routes.transport_manager.configure_smtp")
    def test_configure_smtp_post_redirects(self, mock_configure_smtp):
        mock_configure_smtp.return_value = True
        resp = self.client.post(
            "/test-path/email/config",
            data={
                "action": "configure_smtp",
                "smtp_server": "smtp.example.com",
                "smtp_port": "587",
                "smtp_username": "user@example.com",
                "smtp_password": "secret",
                "use_tls": "true",
            },
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/test-path/email/config")
        mock_configure_smtp.assert_called_once()

    def test_configure_domain_api_sets_manager_state(self):
        resp = self.client.post(
            "/test-path/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk1_test_key",
                "api_secret": "sk1_test_secret",
                "monthly_budget": "33.5",
            },
        )
        assert resp.status_code == 302
        assert domain_rotation_manager.api_client is not None
        assert domain_rotation_manager.monthly_budget == 33.5

    def test_domain_rotate_json_response_shape(self):
        with patch("email_routes.domain_rotation_manager.rotate_domain", return_value="abc123.xyz"):
            resp = self.client.post(
                "/test-path/email/domain/rotate",
                json={},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["domain"] == "abc123.xyz"

