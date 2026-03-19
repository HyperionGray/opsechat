"""
Tests for legal policy route availability and metadata output.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


_app = create_app()


def test_unprefixed_legal_pages_return_200():
    client = _app.test_client()

    assert client.get("/terms").status_code == 200
    assert client.get("/privacy").status_code == 200
    assert client.get("/aup").status_code == 200


def test_prefixed_legal_pages_return_200():
    client = _app.test_client()
    prefix = "/test-path"

    assert client.get(f"{prefix}/terms").status_code == 200
    assert client.get(f"{prefix}/privacy").status_code == 200
    assert client.get(f"{prefix}/aup").status_code == 200


def test_legal_page_content_contains_navigation_and_title():
    client = _app.test_client()
    response = client.get("/privacy")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Privacy Policy" in body
    assert 'href="/terms"' in body
    assert 'href="/privacy"' in body
    assert 'href="/aup"' in body


def test_legal_policies_json_contains_metadata_and_urls():
    client = _app.test_client()
    response = client.get("/legal/policies.json")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload is not None
    assert "policies" in payload
    assert set(payload["policies"].keys()) == {"terms", "privacy", "aup"}
    assert payload["policies"]["privacy"]["url"] == "/privacy"
    assert payload["policies"]["privacy"]["version"] == "0.1.0"


def test_csp_allows_existing_inline_templates():
    client = _app.test_client()
    response = client.get("/chat")

    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
