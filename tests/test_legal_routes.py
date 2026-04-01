"""
Tests for legal policy routes.

Verifies root-level and path-scoped legal pages render and include the
expected policy content under existing security headers.
"""

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "test-scope"
    app.config["hostname"] = "localhost"
    return app


def test_root_terms_page_renders():
    client = _fresh_app().test_client()
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Terms of Service" in body
    assert "Agreement to Terms" in body
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")


def test_root_privacy_page_renders():
    client = _fresh_app().test_client()
    response = client.get("/privacy")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Privacy Policy" in body
    assert "Data We Process" in body


def test_root_aup_page_renders():
    client = _fresh_app().test_client()
    response = client.get("/aup")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Acceptable Use Policy" in body
    assert "Prohibited Activities" in body


def test_scoped_terms_page_requires_matching_path():
    client = _fresh_app().test_client()
    ok = client.get("/test-scope/terms")
    bad = client.get("/wrong/terms")
    assert ok.status_code == 200
    assert bad.status_code == 404


def test_scoped_legal_pages_include_scoped_navigation():
    client = _fresh_app().test_client()
    response = client.get("/test-scope/privacy")
    body = response.data.decode()
    assert response.status_code == 200
    assert 'href="/test-scope/terms"' in body
    assert 'href="/test-scope/privacy"' in body
    assert 'href="/test-scope/aup"' in body
