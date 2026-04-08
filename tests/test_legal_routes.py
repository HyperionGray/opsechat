"""
Integration tests for public legal policy routes.
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


def test_terms_route_returns_200_with_expected_title():
    client = _fresh_app().test_client()
    response = client.get("/terms")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Terms of Service" in body
    assert "Agreement to Terms" in body


def test_aup_route_returns_200_with_expected_title():
    client = _fresh_app().test_client()
    response = client.get("/aup")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Acceptable Use Policy" in body
    assert "Prohibited Activities" in body


def test_privacy_route_returns_200_with_expected_title():
    client = _fresh_app().test_client()
    response = client.get("/privacy")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Privacy Policy" in body
    assert "Data Retention" in body


def test_legal_pages_include_shared_navigation_links():
    client = _fresh_app().test_client()
    response = client.get("/terms")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/terms"' in body
    assert 'href="/aup"' in body
    assert 'href="/privacy"' in body
