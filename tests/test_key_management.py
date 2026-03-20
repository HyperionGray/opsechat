"""
Tests for browser-only key management route and assets.
"""

from app_factory import create_app


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_keys_page_available():
    client = _client()
    response = client.get("/keys")
    assert response.status_code == 200


def test_keys_page_references_static_assets():
    client = _client()
    body = client.get("/keys").get_data(as_text=True)
    assert "/static/key_management.css" in body
    assert "/static/key_management.js" in body


def test_keys_page_has_expected_sections():
    client = _client()
    body = client.get("/keys").get_data(as_text=True)
    assert "Generate New Key" in body
    assert "Import Existing Key" in body
    assert "Export / Backup Key" in body


def test_keys_page_has_security_headers():
    client = _client()
    response = client.get("/keys")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
