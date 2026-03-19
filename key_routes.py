"""
Key management routes for opsechat.

Provides a simple in-memory/session key lifecycle:
- Generate a new AES-256 key
- Import an existing base64-encoded key
- View non-sensitive key metadata
- Export key material for backup
- Delete current key material
"""

import base64
import datetime
import hashlib
import secrets

from flask import jsonify, render_template, request, session


KEY_SESSION_FIELD = "managed_key"
KEY_BYTES = 32  # AES-256


def _key_fingerprint(key_bytes: bytes) -> str:
    """Return a short stable fingerprint for display."""
    digest = hashlib.sha256(key_bytes).hexdigest()
    return digest[:16]


def _build_key_record(key_bytes: bytes, source: str) -> dict:
    """Build a session-safe key record with metadata."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "key_b64": base64.b64encode(key_bytes).decode("ascii"),
        "key_id": secrets.token_hex(8),
        "created_at": now,
        "fingerprint": _key_fingerprint(key_bytes),
        "source": source,
    }


def _get_current_key_record() -> dict:
    """Return the current key record from session if present and valid."""
    key_record = session.get(KEY_SESSION_FIELD)
    if not isinstance(key_record, dict):
        return {}

    required = {"key_b64", "key_id", "created_at", "fingerprint", "source"}
    if not required.issubset(key_record.keys()):
        return {}

    return key_record


def _decode_imported_key(value: str) -> bytes:
    """Decode and validate a base64-encoded key."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Key value is required")

    normalized = value.strip()
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except Exception as exc:
        raise ValueError("Key must be valid base64") from exc

    if len(decoded) != KEY_BYTES:
        raise ValueError(f"Key must be exactly {KEY_BYTES} bytes")

    return decoded


def _metadata_response(key_record: dict) -> dict:
    """Create metadata response payload without exposing key material."""
    return {
        "has_key": True,
        "key_id": key_record["key_id"],
        "created_at": key_record["created_at"],
        "fingerprint": key_record["fingerprint"],
        "source": key_record["source"],
        "algorithm": "AES-256-GCM",
        "key_bytes": KEY_BYTES,
    }


def register_key_routes(app):
    """Register key-management routes with the Flask app."""

    @app.route("/keys", methods=["GET"])
    def keys_page():
        return render_template("keys.html")

    @app.route("/api/keys/status", methods=["GET"])
    def key_status():
        key_record = _get_current_key_record()
        if not key_record:
            return jsonify({"has_key": False, "algorithm": "AES-256-GCM", "key_bytes": KEY_BYTES})
        return jsonify(_metadata_response(key_record))

    @app.route("/api/keys/generate", methods=["POST"])
    def key_generate():
        key_bytes = secrets.token_bytes(KEY_BYTES)
        key_record = _build_key_record(key_bytes, source="generated")
        session[KEY_SESSION_FIELD] = key_record
        return jsonify(_metadata_response(key_record))

    @app.route("/api/keys/import", methods=["POST"])
    def key_import():
        payload = request.get_json(silent=True) or {}
        imported_key = payload.get("key")

        try:
            key_bytes = _decode_imported_key(imported_key)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        key_record = _build_key_record(key_bytes, source="imported")
        session[KEY_SESSION_FIELD] = key_record
        return jsonify(_metadata_response(key_record))

    @app.route("/api/keys/export", methods=["GET"])
    def key_export():
        key_record = _get_current_key_record()
        if not key_record:
            return jsonify({"error": "No key available"}), 404

        response = _metadata_response(key_record)
        response["key"] = key_record["key_b64"]
        return jsonify(response)

    @app.route("/api/keys", methods=["DELETE"])
    def key_delete():
        key_record = _get_current_key_record()
        if key_record:
            # Overwrite session payload before delete for best-effort cleanup.
            key_record["key_b64"] = "X" * len(key_record["key_b64"])
            key_record["fingerprint"] = "0" * len(key_record["fingerprint"])
            session[KEY_SESSION_FIELD] = key_record
            session.pop(KEY_SESSION_FIELD, None)

        return jsonify({"success": True, "has_key": False})
