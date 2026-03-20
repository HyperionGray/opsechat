"""
Tests for HTTP security headers set by the Flask app (app_factory.py).

Verifies: CSP (no unsafe-inline), X-Frame-Options, Referrer-Policy,
X-Content-Type-Options, and Server header suppression.
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
        script_directive = next(
            (part.strip() for part in csp.split(";") if part.strip().startswith("script-src")),
            "",
        )
        # Must not allow unsafe inline execution for script-src.
        assert "unsafe-inline" not in script_directive

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

    def test_csp_uses_request_nonce_for_scripts(self):
        csp = self._headers()["Content-Security-Policy"]
        assert re.search(r"script-src 'self' 'nonce-[^']+'", csp)

    def test_inline_scripts_include_csp_nonce(self):
        resp = self.client.get("/chat")
        csp = resp.headers["Content-Security-Policy"]
        match = re.search(r"script-src 'self' 'nonce-([^']+)'", csp)
        assert match, "Expected nonce in CSP script-src"
        nonce = match.group(1)
        html = resp.get_data(as_text=True)
        assert f'nonce="{nonce}"' in html
