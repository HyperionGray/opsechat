"""
Integration tests for legal policy routes.
"""

from app_factory import create_app


def _fresh_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-legal-routes"
    return app.test_client()


def test_terms_page_renders():
    client = _fresh_client()
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Terms of Service" in body
    assert "Agreement to Terms" in body


def test_privacy_page_renders():
    client = _fresh_client()
    response = client.get("/privacy")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Privacy Policy" in body
    assert "Retention and Deletion" in body


def test_aup_page_renders():
    client = _fresh_client()
    response = client.get("/aup")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Acceptable Use Policy" in body
    assert "Prohibited Activities" in body


def test_legal_pages_allow_trailing_slash():
    client = _fresh_client()
    assert client.get("/terms/").status_code == 200
    assert client.get("/privacy/").status_code == 200
    assert client.get("/aup/").status_code == 200
