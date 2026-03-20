"""
Tests for key management routes.
"""

from app_factory import create_app


def test_keys_page_renders():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/keys")
        assert response.status_code == 200
        assert b"Key Management" in response.data
