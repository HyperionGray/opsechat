"""
Tests for public legal policy routes.
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


class TestLegalRoutes:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_terms_route_returns_200(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Terms of Service" in body

    def test_aup_route_returns_200(self):
        response = self.client.get("/aup")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Acceptable Use Policy" in body

    def test_privacy_route_returns_200(self):
        response = self.client.get("/privacy")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Privacy Policy" in body
        assert "ephemeral" in body.lower()

    def test_policy_pages_have_cross_links(self):
        response = self.client.get("/terms")
        body = response.data.decode("utf-8")
        assert 'href="/aup"' in body
        assert 'href="/privacy"' in body

    def test_policy_links_resolve_internal_aliases(self):
        response = self.client.get("/terms")
        body = response.data.decode("utf-8")
        assert 'href="/privacy"' in body
        assert 'href="/aup"' in body
