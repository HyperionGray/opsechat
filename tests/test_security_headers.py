"""
Tests for HTTP security headers set by the Flask app (app_factory.py).

Verifies:
- CSP profile selection (HTML compatibility vs API strict)
- CSP nonce injection on HTML responses
- X-Frame-Options, Referrer-Policy, X-Content-Type-Options
- Permissions-Policy and Server header suppression
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    """Return a configured test Flask application."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


class TestSecurityHeaders:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def _headers(self, path="/"):
        return self.client.get(path).headers

    def test_csp_header_present(self):
        h = self._headers()
        assert "Content-Security-Policy" in h

    def test_html_csp_uses_compatibility_profile_with_nonce(self):
        csp = self._headers("/chat")["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "unsafe-inline" in csp
        assert "nonce-" in csp

    def test_api_csp_uses_strict_profile(self):
        csp = self._headers("/health")["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "script-src 'none'" in csp
        assert "style-src 'none'" in csp
        assert "form-action 'none'" in csp
        assert "unsafe-inline" not in csp

    def test_x_content_type_options(self):
        h = self._headers("/health")
        assert h.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_deny(self):
        h = self._headers("/health")
        assert h.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_no_referrer(self):
        h = self._headers("/health")
        assert h.get("Referrer-Policy") == "no-referrer"

    def test_permissions_policy_locks_sensitive_features(self):
        h = self._headers("/health")
        assert h.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_server_header_stripped(self):
        h = self._headers("/health")
        assert h.get("Server", "") == ""
