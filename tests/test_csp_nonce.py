"""
Tests for CSP nonce behavior and script-tag nonce injection.
"""

import re

from app_factory import create_app


def _make_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def test_chat_page_injects_nonce_into_script_tags():
    app = _make_app()
    client = app.test_client()

    response = client.get("/chat")
    assert response.status_code == 200

    csp = response.headers.get("Content-Security-Policy", "")
    match = re.search(r"'nonce-([^']+)'", csp)
    assert match, "CSP header must include a nonce in script-src"
    nonce = match.group(1)

    html = response.get_data(as_text=True)
    assert f'<script nonce="{nonce}"' in html
    assert not re.search(r"<script(?![^>]*\bnonce=)", html, re.IGNORECASE)


def test_health_endpoint_keeps_json_structure_with_nonce_csp():
    app = _make_app()
    client = app.test_client()

    response = client.get("/health")
    assert response.status_code == 200
    assert response.is_json
    assert "active_rooms" in response.get_json()

    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self' 'nonce-" in csp
