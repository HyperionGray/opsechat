"""
Tests for HTTP security headers set by the Flask app (app_factory.py).
"""

import os
import re
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
        csp = self._headers("/chat")["Content-Security-Policy"]
        # /chat routes run strict CSP by default and should not allow unsafe inline
        assert "unsafe-inline" not in csp
        assert "script-src 'self' 'nonce-" in csp
        assert "style-src 'self' 'nonce-" in csp

    def test_chat_csp_nonce_changes_per_request(self):
        csp_1 = self._headers("/chat")["Content-Security-Policy"]
        csp_2 = self._headers("/chat")["Content-Security-Policy"]
        nonce_1 = re.search(r"script-src 'self' 'nonce-([^']+)'", csp_1).group(1)
        nonce_2 = re.search(r"script-src 'self' 'nonce-([^']+)'", csp_2).group(1)
        assert nonce_1 != nonce_2

    def test_non_chat_csp_stays_compatible_by_default(self):
        csp = self._headers()["Content-Security-Policy"]
        assert "script-src 'self' 'unsafe-inline'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp

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
