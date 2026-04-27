"""
Integration tests for registered email/admin routes in the real app runtime.
"""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from email_system import email_storage, burner_manager
from email_routes import transport_manager, domain_rotation_manager


def _fresh_app():
    feature_flags = {
        "OPSECHAT_ENABLE_EXTENDED_SERVICES": "1",
        "OPSECHAT_ENABLE_EMAIL_STACK": "1",
        "OPSECHAT_ENABLE_HTTP_MAIL": "1",
    }
    previous = {name: os.environ.get(name) for name in feature_flags}
    try:
        os.environ.update(feature_flags)
        app = create_app()
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    return app


class TestEmailAdminRoutes:
    def setup_method(self):
        self.app = _fresh_app()
        self.client = self.app.test_client()
        email_storage.emails.clear()
        burner_manager.burner_addresses.clear()
        burner_manager.user_burners.clear()
        burner_manager.send_limits.clear()
        burner_manager.custom_domain = None
        domain_rotation_manager.api_client = None
        domain_rotation_manager.api_key = None
        domain_rotation_manager.api_secret = None
        domain_rotation_manager.active_domain = None
        domain_rotation_manager.current_spending = 0.0
        domain_rotation_manager.monthly_budget = 50.0
        domain_rotation_manager.owned_domains = []
        transport_manager.smtp_transport = None
        transport_manager.imap_transport = None

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["_id"] = "testuser"
            sess["color"] = "green"

    def test_email_config_page_renders(self):
        self._login()
        response = self.client.get("/secpath/email/config")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Email System Configuration" in body
        assert "SMTP Configuration" in body
        assert "Domain API" in body

    def test_email_config_post_configures_smtp(self, monkeypatch):
        self._login()
        monkeypatch.setattr(transport_manager, "configure_smtp", Mock(return_value=True))

        response = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_smtp",
                "smtp_server": "smtp.example.com",
                "smtp_port": "587",
                "smtp_username": "user@example.com",
                "smtp_password": "secret",
                "use_tls": "true",
            },
        )

        assert response.status_code == 200
        transport_manager.configure_smtp.assert_called_once()
        assert b"SMTP configuration saved successfully" in response.data

    def test_email_config_post_configures_imap(self, monkeypatch):
        self._login()
        monkeypatch.setattr(transport_manager, "configure_imap", Mock(return_value=True))

        response = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_imap",
                "imap_server": "imap.example.com",
                "imap_port": "993",
                "imap_username": "user@example.com",
                "imap_password": "secret",
                "use_ssl": "true",
            },
        )

        assert response.status_code == 200
        transport_manager.configure_imap.assert_called_once()
        assert b"IMAP configuration saved successfully" in response.data

    def test_email_config_post_requires_domain_credentials(self):
        self._login()
        response = self.client.post(
            "/secpath/email/config",
            data={"action": "configure_domain_api", "api_key": "", "api_secret": ""},
        )
        assert response.status_code == 200
        assert b"Domain API key and secret are required" in response.data

    def test_email_config_post_configures_domain_api(self):
        self._login()
        response = self.client.post(
            "/secpath/email/config",
            data={
                "action": "configure_domain_api",
                "api_key": "pk1_test",
                "api_secret": "sk1_test",
                "monthly_budget": "75",
            },
        )
        assert response.status_code == 200
        assert domain_rotation_manager.get_config()["configured"] is True
        assert domain_rotation_manager.get_config()["monthly_budget"] == 75.0
        assert b"Domain API configuration saved successfully" in response.data

    def test_email_send_api_rejects_invalid_recipient(self):
        self._login()
        response = self.client.post(
            "/secpath/email/send",
            json={"to": "not-an-email", "subject": "Hello", "body": "World"},
        )
        assert response.status_code == 400
        assert response.get_json()["success"] is False

    def test_email_send_api_sends_and_stores_email(self, monkeypatch):
        self._login()
        monkeypatch.setattr(transport_manager, "send_email", Mock(return_value=True))

        response = self.client.post(
            "/secpath/email/send",
            json={
                "from": "sender@example.com",
                "to": "recipient@example.com",
                "subject": "Hello",
                "body": "World",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        emails = email_storage.get_emails("testuser")
        assert len(emails) == 1
        assert emails[0]["subject"] == "Hello"
        assert emails[0]["sent"] is True

    def test_email_receive_api_returns_json_and_stores_emails(self, monkeypatch):
        self._login()
        monkeypatch.setattr(
            transport_manager,
            "receive_emails",
            Mock(return_value=[{
                "from": "sender@example.com",
                "to": "testuser@example.com",
                "subject": "Inbox hello",
                "body": "body",
                "headers": {},
            }]),
        )

        response = self.client.post(
            "/secpath/email/receive",
            json={"limit": 5, "unread_only": True},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["count"] == 1
        emails = email_storage.get_emails("testuser")
        assert len(emails) == 1
        assert emails[0]["subject"] == "Inbox hello"

    def test_email_domain_rotate_sets_custom_domain(self, monkeypatch):
        self._login()
        monkeypatch.setattr(
            domain_rotation_manager,
            "rotate_domain",
            Mock(return_value={
                "success": True,
                "active_domain": "fresh-example.xyz",
                "message": "Rotated",
            }),
        )

        response = self.client.post("/secpath/email/domain/rotate", json={})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert burner_manager.get_custom_domain() == "fresh-example.xyz"

    def test_spoof_test_detect_flow_renders_results(self):
        self._login()
        response = self.client.post(
            "/secpath/email/security/spoof-test",
            data={
                "test_type": "detect",
                "test_email": "admin@legitimate.example.com",
                "legitimate_domain": "example.com",
            },
        )
        assert response.status_code == 200
        assert b"Risk Score" in response.data

    def test_spoof_test_generate_flow_renders_variants(self):
        self._login()
        response = self.client.post(
            "/secpath/email/security/spoof-test",
            data={"test_type": "generate", "target_domain": "example.com"},
        )
        assert response.status_code == 200
        assert b"Spoofing Variants Generated" in response.data

    def test_phishing_sim_enable_and_generate_email(self):
        self._login()
        enable_response = self.client.post(
            "/secpath/email/security/phishing-sim",
            data={"action": "enable"},
        )
        assert enable_response.status_code == 200

        response = self.client.post(
            "/secpath/email/security/phishing-sim",
            data={"action": "generate", "template": "generic"},
        )

        assert response.status_code == 200
        assert b"Phishing simulation email added to your inbox" in response.data
        emails = email_storage.get_emails("testuser")
        assert len(emails) == 1
        assert emails[0]["is_phishing_sim"] is True
