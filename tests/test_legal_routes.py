"""
Tests for legal policy endpoints served by app_factory/create_app.
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


class TestLegalPolicyEndpoints:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_terms_endpoint_returns_200(self):
        resp = self.client.get("/terms")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Terms of Service" in body
        assert "Policy navigation" in body

    def test_aup_endpoint_returns_200(self):
        resp = self.client.get("/aup")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Acceptable Use Policy" in body
        assert "Policy navigation" in body

    def test_privacy_endpoint_returns_200(self):
        resp = self.client.get("/privacy")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Privacy Policy" in body
        assert "Policy navigation" in body

    def test_legal_pages_have_security_headers(self):
        resp = self.client.get("/privacy")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "no-referrer"
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "script-src 'self'" in csp
        assert "unsafe-inline" not in csp
