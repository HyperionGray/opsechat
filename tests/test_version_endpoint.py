"""
Tests for the /version endpoint.
"""

import sys
import types


def _install_closed_roster_stub():
    """Install a minimal runtime stub when closed_roster_room.py is absent."""
    if "closed_roster_room" in sys.modules:
        return

    module = types.ModuleType("closed_roster_room")
    module.OPENPGP_ENVELOPE_TYPE = "closed_roster_openpgp_v1"

    class ClosedRosterState:
        def __init__(self, room_id):
            self.room_id = room_id

        def bootstrap(self, members):
            return {"active_epoch": None, "members": members}

        def serialize(self):
            return {
                "mode": module.OPENPGP_ENVELOPE_TYPE,
                "active_epoch": None,
                "policy": {
                    "immutable_roster": True,
                    "shared_room_keys_supported": False,
                },
            }

        def validate_posted_envelope(self, payload):
            return payload

    module.ClosedRosterState = ClosedRosterState
    sys.modules["closed_roster_room"] = module


def test_version_endpoint_returns_version_field():
    _install_closed_roster_stub()
    from app_factory import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/version")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, dict)
    assert "version" in data
    assert isinstance(data["version"], str)
    assert data["version"]
