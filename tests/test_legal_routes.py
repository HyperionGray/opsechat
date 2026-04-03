"""
Tests for legal policy routes served by app_factory/legal_routes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


def test_terms_route_available_and_contains_expected_heading():
    client = _fresh_app().test_client()
    response = client.get("/terms")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Terms of Service" in body
    assert "Hyperion Gray LLC" in body


def test_aup_route_available_and_contains_expected_heading():
    client = _fresh_app().test_client()
    response = client.get("/aup")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Acceptable Use Policy" in body
    assert "Prohibited Activities" in body


def test_privacy_route_available_and_contains_expected_heading():
    client = _fresh_app().test_client()
    response = client.get("/privacy")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Privacy Policy" in body
    assert "Data We Process" in body


def test_legal_routes_include_security_headers():
    client = _fresh_app().test_client()
    response = client.get("/privacy")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
