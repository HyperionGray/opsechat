"""
Tests for email configuration and domain rotation routes.
"""
from unittest.mock import patch

from app_factory import create_app
from email_transport import transport_manager
from domain_manager import domain_rotation_manager


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    return app


def _reset_transport_and_domain_state():
    transport_manager.smtp_transport = None
    transport_manager.imap_transport = None
    domain_rotation_manager.api_client = None
    domain_rotation_manager.provider = None
    domain_rotation_manager.current_spending = 0.0
    domain_rotation_manager.owned_domains = []
    domain_rotation_manager.active_domain = None
    domain_rotation_manager._api_key = None
    domain_rotation_manager._api_secret = None


class TestEmailConfigRoutes:
    def setup_method(self):
        _reset_transport_and_domain_state()
        self.app = _fresh_app()
        self.client = self.app.test_client()

        with self.client.session_transaction() as sess:
            sess["_id"] = "email-config-user"
            sess["color"] = "green"

    def teardown_method(self):
        _reset_transport_and_domain_state()

    def test_email_config_page_renders(self):
        resp = self.client.get("/secpath/email/config")
        assert resp.status_code == 200
        assert b"Email System Configuration" in resp.data

    @patch("email_routes.transport_manager.configure_smtp", return_value=True)
    def test_configure_smtp_success(self, _mock_configure_smtp):
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
        assert b"SMTP configuration saved successfully" in resp.data

    @patch("email_routes.transport_manager.configure_imap", return_value=True)
    def test_configure_imap_success(self, _mock_configure_imap):
        resp = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_imap",
                "imap_server": "imap.example.com",
                "imap_port": "993",
                "imap_username": "user@example.com",
                "imap_password": "secret",
                "use_ssl": "on",
            },
        )
        assert resp.status_code == 200
        assert b"IMAP configuration saved successfully" in resp.data

    @patch("email_routes.domain_rotation_manager.configure")
    def test_configure_domain_api_success(self, mock_configure):
        mock_configure.return_value = {"configured": True}
        resp = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk1_example",
                "api_secret": "sk1_example",
                "monthly_budget": "25.00",
            },
        )
        assert resp.status_code == 200
        assert b"Domain configuration saved successfully" in resp.data

    @patch("email_routes.transport_manager.receive_emails")
    def test_receive_route_fetches_and_stores_mail(self, mock_receive_emails):
        mock_receive_emails.return_value = [
            {
                "from": "sender@example.com",
                "to": "email-config-user@example.com",
                "subject": "Hello",
                "body": "Test",
                "headers": {},
                "is_pgp": False,
            }
        ]
        resp = self.client.post(
            "/secpath/email/receive",
            data={"limit": "5", "unread_only": "true"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/secpath/email")

    @patch("email_routes.domain_rotation_manager.rotate_domain")
    def test_domain_rotate_route_redirects_back_to_config(self, mock_rotate):
        mock_rotate.return_value = "newdomain.xyz"
        resp = self.client.post("/secpath/email/domain/rotate", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/secpath/email/config")
