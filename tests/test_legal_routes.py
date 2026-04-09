"""
Tests for legal policy routes and legal footer links.
"""

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


def test_terms_route_serves_policy_page():
    client = _fresh_app().test_client()
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Terms of Service" in body
    assert "docs/legal/TERMS_OF_SERVICE.md" in body


def test_privacy_route_serves_policy_page():
    client = _fresh_app().test_client()
    response = client.get("/privacy")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Privacy Policy" in body
    assert "docs/legal/PRIVACY_POLICY.md" in body


def test_aup_route_serves_policy_page():
    client = _fresh_app().test_client()
    response = client.get("/aup")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Acceptable Use Policy" in body
    assert "docs/legal/ACCEPTABLE_USE_POLICY.md" in body


def test_policy_page_has_cross_policy_navigation_links():
    client = _fresh_app().test_client()
    response = client.get("/privacy")
    body = response.data.decode()
    assert 'href="/terms"' in body
    assert 'href="/privacy"' in body
    assert 'href="/aup"' in body


def test_simple_chat_index_footer_includes_legal_links():
    client = _fresh_app().test_client()
    response = client.get("/chat")
    assert response.status_code == 200
    body = response.data.decode()
    assert 'href="/terms"' in body
    assert 'href="/privacy"' in body
    assert 'href="/aup"' in body
