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
        # Script policy must never allow unsafe-inline JavaScript.
        script_src = next(
            (part.strip() for part in csp.split(";") if part.strip().startswith("script-src")),
            "",
        )
        assert script_src
        assert "'unsafe-inline'" not in script_src
        assert "nonce-" in script_src

    def test_csp_style_policy_allows_legacy_inline_styles(self):
        csp = self._headers()["Content-Security-Policy"]
        style_src = next(
            (part.strip() for part in csp.split(";") if part.strip().startswith("style-src")),
            "",
        )
        assert style_src
        assert "'unsafe-inline'" in style_src

    def test_inline_script_templates_emit_nonce_attribute(self):
        app = _fresh_app()
        app.config["path"] = "nonce-test-path"
        app.config["hostname"] = "localhost"
        client = app.test_client()
        response = client.get("/nonce-test-path/landing/auto")
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert '<script nonce="' in body

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
