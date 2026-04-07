"""
Integration tests for email configuration routes.
"""
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    return app


class TestEmailConfigRoutes:
    def setup_method(self):
        self.app = _fresh_app()
        self.client = self.app.test_client()

    def _establish_session(self):
        self.client.get(f"/{self.app.config['path']}/email")

    def test_email_config_get_renders(self):
        resp = self.client.get(f"/{self.app.config['path']}/email/config")
        assert resp.status_code == 200
        assert b"Email System Configuration" in resp.data

    @patch("email_routes.transport_manager.configure_smtp")
    @patch("email_routes.transport_manager.is_configured")
    def test_configure_smtp_action_success(self, mock_is_configured, mock_configure_smtp):
        self._establish_session()
        mock_is_configured.return_value = {"smtp": True, "imap": False}
        mock_configure_smtp.return_value = True

        resp = self.client.post(
            f"/{self.app.config['path']}/email/config",
            data={
                "action": "configure_smtp",
                "smtp_server": "smtp.example.com",
                "smtp_port": "587",
                "smtp_username": "alice@example.com",
                "smtp_password": "secret",
                "use_tls": "true",
            },
        )

        assert resp.status_code == 200
        mock_configure_smtp.assert_called_once()
        assert b"SMTP configured successfully" in resp.data

    @patch("email_routes.transport_manager.configure_imap")
    @patch("email_routes.transport_manager.is_configured")
    def test_configure_imap_action_success(self, mock_is_configured, mock_configure_imap):
        self._establish_session()
        mock_is_configured.return_value = {"smtp": False, "imap": True}
        mock_configure_imap.return_value = True

        resp = self.client.post(
            f"/{self.app.config['path']}/email/config",
            data={
                "action": "configure_imap",
                "imap_server": "imap.example.com",
                "imap_port": "993",
                "imap_username": "alice@example.com",
                "imap_password": "secret",
                "use_ssl": "true",
            },
        )

        assert resp.status_code == 200
        mock_configure_imap.assert_called_once()
        assert b"IMAP configured successfully" in resp.data

    @patch("email_routes.domain_rotation_manager.configure")
    @patch("email_routes.transport_manager.is_configured")
    def test_configure_domain_action_success(self, mock_is_configured, mock_domain_configure):
        self._establish_session()
        mock_is_configured.return_value = {"smtp": False, "imap": False}
        mock_domain_configure.return_value = {"configured": True}

        resp = self.client.post(
            f"/{self.app.config['path']}/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk1_test",
                "api_secret": "sk1_test",
                "monthly_budget": "20",
            },
        )

        assert resp.status_code == 200
        mock_domain_configure.assert_called_once_with(
            api_key="pk1_test",
            secret_key="sk1_test",
            monthly_budget=20.0,
        )
        assert b"Domain API configured successfully" in resp.data

    @patch("email_routes.transport_manager.receive_emails")
    @patch("email_routes.email_storage.add_email")
    def test_receive_route_stores_emails_and_redirects(self, mock_add_email, mock_receive_emails):
        self._establish_session()
        mock_receive_emails.return_value = [
            {"from": "a@example.com", "to": "b@example.com", "subject": "s", "body": "hello"},
            {"from": "c@example.com", "to": "d@example.com", "subject": "x", "body": "world"},
        ]

        resp = self.client.post(
            f"/{self.app.config['path']}/email/receive",
            data={"limit": "10", "unread_only": "true"},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        mock_receive_emails.assert_called_once_with(limit=10, unread_only=True)
        assert mock_add_email.call_count == 2

    @patch("email_routes.transport_manager.receive_emails")
    @patch("email_routes.email_storage.add_email")
    def test_receive_route_defaults_to_all_and_no_limit(self, mock_add_email, mock_receive_emails):
        self._establish_session()
        mock_receive_emails.return_value = []

        resp = self.client.post(
            f"/{self.app.config['path']}/email/receive",
            data={"limit": "not-a-number", "unread_only": "false"},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        mock_receive_emails.assert_called_once_with(limit=None, unread_only=False)
        assert mock_add_email.call_count == 0

    @patch("email_routes.domain_rotation_manager.rotate_domain_with_result")
    def test_domain_rotate_route_redirects_with_flash_message(self, mock_rotate):
        self._establish_session()
        mock_rotate.return_value = {"success": True, "domain": "newdomain.xyz"}

        resp = self.client.post(
            f"/{self.app.config['path']}/email/domain/rotate",
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/{self.app.config['path']}/email/config")

        follow = self.client.get(resp.headers["Location"])
        assert follow.status_code == 200
        assert b"Domain rotation successful: newdomain.xyz" in follow.data
