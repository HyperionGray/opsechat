"""
Tests for /keys key management page.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


def test_keys_page_returns_200():
    client = _fresh_app().test_client()
    response = client.get("/keys")
    assert response.status_code == 200


def test_keys_page_references_external_assets_only():
    client = _fresh_app().test_client()
    response = client.get("/keys")
    body = response.data.decode()

    assert "/static/keys.css" in body
    assert "/static/openpgp.min.js" in body
    assert "/static/keys.js" in body
    assert "<style>" not in body
    assert "onclick=" not in body
