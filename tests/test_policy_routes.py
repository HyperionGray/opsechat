"""
Tests for legal policy display routes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


class TestPolicyRoutes:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_terms_route_returns_policy_page(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        assert b"Terms of Service" in response.data

    def test_privacy_route_returns_policy_page(self):
        response = self.client.get("/privacy")
        assert response.status_code == 200
        assert b"Privacy Policy" in response.data

    def test_aup_route_returns_policy_page(self):
        response = self.client.get("/aup")
        assert response.status_code == 200
        assert b"Acceptable Use Policy" in response.data

    def test_policy_pages_render_source_markdown_text(self):
        response = self.client.get("/privacy")
        assert b"This Privacy Policy explains how opsechat handles information" in response.data
