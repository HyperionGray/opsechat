"""
Tests for domain rotation CLI state persistence helpers.
"""
import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_owned_domains_datetime_round_trip():
    owned_domains = [
        {
            "domain": "roundtrip.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 3, 1, 12, 30, 45),
            "expires_at": datetime(2027, 3, 1, 12, 30, 45),
        }
    ]

    serialized = cli._serialize_owned_domains(owned_domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = cli._deserialize_owned_domains(serialized)
    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["domain"] == "roundtrip.xyz"


def test_save_manager_state_writes_json_serializable_datetimes(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager()
    manager.current_spending = 2.99
    manager.active_domain = "persisted.xyz"
    manager.owned_domains = [
        {
            "domain": "persisted.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 3, 2, 10, 0, 0),
            "expires_at": datetime(2027, 3, 2, 10, 0, 0),
        }
    ]

    cli.save_manager_state(manager, {})

    data = json.loads(config_file.read_text())
    assert data["active_domain"] == "persisted.xyz"
    assert isinstance(data["owned_domains"][0]["purchased_at"], str)
    assert data["owned_domains"][0]["purchased_at"].startswith("2026-03-02T10:00:00")
