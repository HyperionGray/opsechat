"""
Integration tests for key management routes.
"""

import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from email_system import email_storage


def _build_test_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["path"] = "test-path-keys"
    app.config["hostname"] = "localhost"
    return app


def _reset_key_storage():
    email_storage.user_keys.clear()


def test_keys_page_requires_correct_path():
    _reset_key_storage()
    app = _build_test_app()
    client = app.test_client()

    response = client.get("/wrong-path/keys")
    assert response.status_code == 404


def test_key_generate_and_render():
    _reset_key_storage()
    app = _build_test_app()
    client = app.test_client()

    response = client.post(
        "/test-path-keys/keys/generate",
        data={"label": "Primary ops key"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Primary ops key" in response.data
    assert b"Key generated successfully" in response.data


def test_key_import_validation_message():
    _reset_key_storage()
    app = _build_test_app()
    client = app.test_client()

    response = client.post(
        "/test-path-keys/keys/import",
        data={"label": "Invalid", "key_material": "short"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Import failed: Key material is too short" in response.data


def test_key_export_and_delete_lifecycle():
    _reset_key_storage()
    app = _build_test_app()
    client = app.test_client()

    client.post(
        "/test-path-keys/keys/generate",
        data={"label": "Temporary key"},
        follow_redirects=True,
    )

    assert email_storage.user_keys
    user_id = next(iter(email_storage.user_keys.keys()))
    key_id = email_storage.user_keys[user_id][0]["id"]

    export_response = client.get(f"/test-path-keys/keys/export/{key_id}")
    assert export_response.status_code == 200
    payload = export_response.get_json()
    assert payload["id"] == key_id
    assert "key_material" in payload

    delete_response = client.post(
        f"/test-path-keys/keys/delete/{key_id}",
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert b"Key deleted successfully" in delete_response.data
    assert email_storage.user_keys[user_id] == []
