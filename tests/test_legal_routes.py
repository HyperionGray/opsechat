"""
Tests for legal policy routes and policy metadata endpoint.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-legal-routes"
    return app.test_client()


def test_terms_page_serves_policy_content_and_headers():
    client = _client()
    response = client.get("/terms")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Terms of Service" in body
    assert "docs/legal/TERMS_OF_SERVICE.md" in body
    assert "X-Policy-Version" in response.headers
    assert response.headers["X-Policy-Version"]


def test_aup_page_serves_policy_content_and_headers():
    client = _client()
    response = client.get("/aup")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Acceptable Use Policy" in body
    assert "docs/legal/ACCEPTABLE_USE_POLICY.md" in body
    assert response.headers["X-Policy-Version"]


def test_privacy_page_serves_policy_content_and_headers():
    client = _client()
    response = client.get("/privacy")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Privacy Policy" in body
    assert "docs/legal/PRIVACY_POLICY.md" in body
    assert response.headers["X-Policy-Version"] == "1.0 (Draft - Alpha Release)"


def test_policy_versions_endpoint_returns_all_policies():
    client = _client()
    response = client.get("/policy/versions")
    data = response.get_json()

    assert response.status_code == 200
    assert "policies" in data

    policies = data["policies"]
    assert set(policies.keys()) == {"terms", "aup", "privacy"}

    assert policies["terms"]["route"] == "/terms"
    assert policies["aup"]["route"] == "/aup"
    assert policies["privacy"]["route"] == "/privacy"

    assert policies["terms"]["source"] == "docs/legal/TERMS_OF_SERVICE.md"
    assert policies["aup"]["source"] == "docs/legal/ACCEPTABLE_USE_POLICY.md"
    assert policies["privacy"]["source"] == "docs/legal/PRIVACY_POLICY.md"
