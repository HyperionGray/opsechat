"""
Tests for policy page routes and rendering.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_terms_route_returns_200():
    client = _fresh_client()
    response = client.get("/terms")
    assert response.status_code == 200


def test_aup_route_returns_200():
    client = _fresh_client()
    response = client.get("/aup")
    assert response.status_code == 200


def test_privacy_route_returns_200():
    client = _fresh_client()
    response = client.get("/privacy")
    assert response.status_code == 200


def test_policies_index_returns_200():
    client = _fresh_client()
    response = client.get("/policies")
    assert response.status_code == 200


def test_policy_pages_include_navigation_links():
    client = _fresh_client()
    response = client.get("/terms")
    body = response.data.decode("utf-8")
    assert "/terms" in body
    assert "/aup" in body
    assert "/privacy" in body
    assert "/policies" in body


def test_policies_index_lists_all_documents():
    client = _fresh_client()
    response = client.get("/policies")
    body = response.data.decode("utf-8")
    assert "Terms of Service" in body
    assert "Acceptable Use Policy" in body
    assert "Privacy Policy" in body

