"""
Tests for HTTP security headers set by the Flask app (app_factory.py).

Verifies: CSP nonce enforcement for scripts, X-Frame-Options,
Referrer-Policy, X-Content-Type-Options, and Server header suppression.
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
        csp = self._headers()["Content-Security-Policy"]
        directives = [d.strip() for d in csp.split(";") if d.strip()]
        script_src = next((d for d in directives if d.startswith("script-src ")), "")
        assert script_src, "script-src directive missing"
        # Must not allow inline scripts, must allow nonce-based inline scripts.
        assert "'unsafe-inline'" not in script_src
        assert "'nonce-" in script_src

    def test_csp_uses_per_request_script_nonce(self):
        csp = self._headers()["Content-Security-Policy"]
        match = re.search(r"script-src 'self' 'nonce-([^']+)'", csp)
        assert match is not None
        assert match.group(1)

    def test_csp_nonce_rotates_between_requests(self):
        csp_1 = self._headers()["Content-Security-Policy"]
        csp_2 = self._headers()["Content-Security-Policy"]
        nonce_1 = re.search(r"script-src 'self' 'nonce-([^']+)'", csp_1).group(1)
        nonce_2 = re.search(r"script-src 'self' 'nonce-([^']+)'", csp_2).group(1)
        assert nonce_1 != nonce_2

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
