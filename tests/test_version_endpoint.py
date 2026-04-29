"""
Tests for the /version endpoint added in app_factory.
"""

import os
import sys
import types

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_closed_roster_stub():
    """Install a lightweight stub for closed_roster_room if missing."""
    if "closed_roster_room" in sys.modules:
        return

    stub = types.ModuleType("closed_roster_room")

    class ClosedRosterState:  # pragma: no cover - runtime shim for import compatibility
        def __init__(self, room_id):
            self.room_id = room_id

    stub.ClosedRosterState = ClosedRosterState
    stub.OPENPGP_ENVELOPE_TYPE = "application/opsechat-openpgp"
    sys.modules["closed_roster_room"] = stub


def _build_test_client():
    _install_closed_roster_stub()
    from app_factory import create_app

    app = create_app()
    return app.test_client()


def test_version_endpoint_returns_json_payload():
    client = _build_test_client()
    response = client.get("/version")

    assert response.status_code == 200
    assert response.content_type == "application/json"

    data = response.get_json()
    assert data is not None
    assert isinstance(data.get("version"), str)
    assert data["version"] != ""


def test_version_endpoint_applies_security_headers():
    client = _build_test_client()
    response = client.get("/version")

    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Server"] == ""
    assert response.headers["Date"] == ""
