"""
Security header tests for app_factory response middleware.
"""

import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _response_for_root(monkeypatch, mode=None):
    """Create a test app with an optional CSP mode and fetch /."""
    if mode is None:
        monkeypatch.delenv("OPSECHAT_CSP_MODE", raising=False)
    else:
        monkeypatch.setenv("OPSECHAT_CSP_MODE", mode)

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        return client.get("/")


def test_security_headers_are_present(monkeypatch):
    response = _response_for_root(monkeypatch)
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("Content-Security-Policy")


def test_csp_defaults_to_compat_mode(monkeypatch):
    response = _response_for_root(monkeypatch)
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_csp_strict_mode_disables_inline(monkeypatch):
    response = _response_for_root(monkeypatch, mode="strict")
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self';" in csp
    assert "style-src 'self';" in csp
    assert "'unsafe-inline'" not in csp


def test_invalid_csp_mode_falls_back_to_compat(monkeypatch):
    response = _response_for_root(monkeypatch, mode="invalid-value")
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
