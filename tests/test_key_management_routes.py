"""
Tests for key management routes and page wiring.
"""

import pytest

from app_factory import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with app.app_context():
            yield c


def test_keys_page_returns_200(client):
    response = client.get("/keys")
    assert response.status_code == 200


def test_keys_page_includes_management_sections(client):
    response = client.get("/keys")
    body = response.get_data(as_text=True)

    assert "OpSecChat Key Management" in body
    assert "Generate a New Key Pair" in body
    assert "Import Private Key" in body
    assert "Import Public Keys for Recipients" in body
    assert "Your private key stays in your browser." in body


def test_keys_page_loads_required_scripts(client):
    response = client.get("/keys")
    body = response.get_data(as_text=True)

    assert 'static/openpgp.min.js' in body
    assert 'static/pgp-manager.js' in body
    assert 'static/key-management.js' in body
