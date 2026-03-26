"""
Tests for HTTP security headers set by the Flask app (app_factory.py).

Verifies: CSP (no unsafe-inline), X-Frame-Options, Referrer-Policy,
X-Content-Type-Options, and Server header suppression.
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

    def test_csp_disallows_inline_scripts(self):
        csp = self._headers()["Content-Security-Policy"]
        # Must not contain 'unsafe-inline' for scripts
        assert "unsafe-inline" not in csp
        assert "script-src 'self' 'nonce-" in csp
        assert "style-src 'self' 'nonce-" in csp

    def test_inline_script_and_style_have_nonce(self):
        app = _fresh_app()
        app.config["path"] = "secpath"
        client = app.test_client()
        r = client.get("/secpath/mail")
        body = r.get_data(as_text=True)
        assert '<script nonce="' in body
        assert '<style nonce="' in body

    def test_x_content_type_options(self):
        h = self._headers()
        assert h.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_deny(self):
        h = self._headers()
        assert h.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_no_referrer(self):
        h = self._headers()
        assert h.get("Referrer-Policy") == "no-referrer"

    def test_server_header_stripped(self):
        h = self._headers()
        assert h.get("Server", "") == ""
