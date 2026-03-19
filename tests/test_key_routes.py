"""
Tests for key management routes.
"""

import base64
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_keys_page_available():
    client = _client()
    response = client.get("/keys")
    assert response.status_code == 200
    assert b"Key Management" in response.data


def test_generate_key_sets_session_state_and_export_works():
    client = _client()

    generate = client.post("/api/keys/generate")
    assert generate.status_code == 200
    generated_payload = generate.get_json()
    assert generated_payload["has_key"] is True
    assert generated_payload["algorithm"] == "AES-256-GCM"
    assert generated_payload["key_bytes"] == 32
    assert generated_payload["source"] == "generated"
    assert generated_payload.get("key_id")
    assert generated_payload.get("fingerprint")

    status = client.get("/api/keys/status")
    assert status.status_code == 200
    status_payload = status.get_json()
    assert status_payload["has_key"] is True
    assert status_payload["key_id"] == generated_payload["key_id"]
    assert status_payload["source"] == "generated"

    exported = client.get("/api/keys/export")
    assert exported.status_code == 200
    export_payload = exported.get_json()
    decoded = base64.b64decode(export_payload["key"], validate=True)
    assert len(decoded) == 32
    assert export_payload["key_id"] == generated_payload["key_id"]


def test_import_valid_base64_key():
    client = _client()
    valid_key = base64.b64encode(b"A" * 32).decode("ascii")

    imported = client.post("/api/keys/import", json={"key": valid_key})
    assert imported.status_code == 200
    import_payload = imported.get_json()
    assert import_payload["has_key"] is True
    assert import_payload["source"] == "imported"
    assert import_payload["key_bytes"] == 32

    exported = client.get("/api/keys/export")
    export_payload = exported.get_json()
    assert export_payload["key"] == valid_key


def test_import_rejects_invalid_key():
    client = _client()

    bad_base64 = client.post("/api/keys/import", json={"key": "this-is-not-base64"})
    assert bad_base64.status_code == 400
    assert "error" in bad_base64.get_json()

    wrong_length = base64.b64encode(b"short").decode("ascii")
    bad_length = client.post("/api/keys/import", json={"key": wrong_length})
    assert bad_length.status_code == 400
    assert "error" in bad_length.get_json()


def test_delete_key_clears_session_state():
    client = _client()
    client.post("/api/keys/generate")

    delete_response = client.delete("/api/keys")
    assert delete_response.status_code == 200
    assert delete_response.get_json()["success"] is True

    status = client.get("/api/keys/status")
    status_payload = status.get_json()
    assert status_payload["has_key"] is False

    export = client.get("/api/keys/export")
    assert export.status_code == 404
