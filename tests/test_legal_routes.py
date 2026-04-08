"""
Tests for legal policy routes (/terms, /privacy, /aup).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
import legal_routes


def _fresh_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_terms_page_returns_200():
    client = _fresh_client()
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Terms of Service" in body
    assert "Agreement to Terms" in body


def test_aup_page_returns_200():
    client = _fresh_client()
    response = client.get("/aup")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Acceptable Use Policy" in body
    assert "Permitted Use" in body


def test_privacy_page_returns_200():
    client = _fresh_client()
    response = client.get("/privacy")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Privacy Policy" in body
    assert "Core Privacy Design" in body


def test_policy_pages_include_navigation_links():
    client = _fresh_client()
    for path in ("/terms", "/privacy", "/aup"):
        response = client.get(path)
        body = response.data.decode("utf-8")
        assert response.status_code == 200
        assert 'href="/terms"' in body
        assert 'href="/privacy"' in body
        assert 'href="/aup"' in body
        assert 'href="/chat"' in body


def test_privacy_slash_variant_returns_200():
    client = _fresh_client()
    response = client.get("/privacy/")
    assert response.status_code == 200


def test_missing_policy_file_shows_unavailable_message(monkeypatch):
    client = _fresh_client()

    monkeypatch.setitem(
        legal_routes.POLICY_DOCS,
        "privacy",
        ("Privacy Policy", "__definitely_missing_policy__.md"),
    )

    response = client.get("/privacy")
    body = response.data.decode("utf-8")

    assert response.status_code == 503
    assert "Policy document temporarily unavailable" in body
