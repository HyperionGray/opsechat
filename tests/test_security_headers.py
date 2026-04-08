"""
Tests for HTTP security headers set by the Flask app (app_factory.py).

Verifies: CSP (no unsafe-inline), X-Frame-Options, Referrer-Policy,
X-Content-Type-Options, and Server header suppression.
"""

import os
import sys
import pytest

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

    def test_template_audit_strict_mode_blocks_on_findings(self, monkeypatch):
        monkeypatch.setenv("TEMPLATE_AUDIT_MODE", "strict")
        with pytest.raises(RuntimeError):
            create_app()
        monkeypatch.delenv("TEMPLATE_AUDIT_MODE", raising=False)

    def test_template_audit_off_mode_allows_startup(self, monkeypatch):
        monkeypatch.setenv("TEMPLATE_AUDIT_MODE", "off")
        app = create_app()
        assert app is not None
        monkeypatch.delenv("TEMPLATE_AUDIT_MODE", raising=False)
