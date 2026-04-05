"""
Tests for legal policy routes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app.test_client()


def test_terms_page_renders():
    response = _client().get("/terms")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Terms of Service" in body
    assert "Acceptable Use Policy" in body
    assert "Content-Security-Policy" in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_privacy_page_renders():
    response = _client().get("/privacy")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Privacy Policy" in body
    assert "Core Privacy Model" in body
    assert 'href="/terms"' in body
    assert 'href="/aup"' in body


def test_aup_page_renders():
    response = _client().get("/aup")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Acceptable Use Policy" in body
    assert "Prohibited Activities" in body


def test_missing_legal_route_is_404():
    response = _client().get("/legal/does-not-exist")
    assert response.status_code == 404

