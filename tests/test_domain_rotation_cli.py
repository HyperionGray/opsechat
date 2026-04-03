"""
Tests for domain_rotation_cli persistence helpers.
"""

import json
from datetime import datetime, timezone

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_serialize_and_deserialize_domain_records_roundtrip():
    purchased_at = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)
    expires_at = datetime(2027, 4, 3, 15, 0, tzinfo=timezone.utc)

    records = [
        {
            "domain": "example.xyz",
            "price": 1.23,
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }
    ]

    serialized = cli._serialize_domain_records(records)
    assert serialized[0]["purchased_at"] == purchased_at.isoformat()
    assert serialized[0]["expires_at"] == expires_at.isoformat()

    deserialized = cli._deserialize_domain_records(serialized)
    assert deserialized[0]["purchased_at"] == purchased_at
    assert deserialized[0]["expires_at"] == expires_at


def test_deserialize_tolerates_invalid_datetime_values():
    records = [
        {
            "domain": "invalid.xyz",
            "purchased_at": "not-a-date",
            "expires_at": None,
        }
    ]

    deserialized = cli._deserialize_domain_records(records)
    assert deserialized[0]["purchased_at"] is None
    assert deserialized[0]["expires_at"] is None


def test_save_manager_state_and_get_manager_roundtrip(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=25.0)
    manager.current_spending = 4.5
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 1.5,
            "purchased_at": datetime(2026, 4, 3, 15, 1, tzinfo=timezone.utc),
            "expires_at": datetime(2027, 4, 3, 15, 1, tzinfo=timezone.utc),
        }
    ]

    initial_config = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "monthly_budget": 25.0,
    }
    cli.save_manager_state(manager, initial_config)

    raw = json.loads(config_file.read_text())
    assert isinstance(raw["owned_domains"][0]["purchased_at"], str)
    assert isinstance(raw["owned_domains"][0]["expires_at"], str)

    loaded_manager, loaded_config = cli.get_manager()
    assert loaded_manager.current_spending == 4.5
    assert loaded_manager.active_domain == "active.xyz"
    assert loaded_manager.monthly_budget == 25.0
    assert isinstance(loaded_manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(loaded_manager.owned_domains[0]["expires_at"], datetime)
    assert loaded_config["api_key"] == "test_key"


def test_get_manager_tolerates_invalid_current_spending(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(
            {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "monthly_budget": 50.0,
                "current_spending": "invalid",
                "owned_domains": [],
            }
        )
    )

    manager, _ = cli.get_manager()
    assert manager.current_spending == 0.0


def test_format_datetime_returns_unknown_for_invalid():
    assert cli._format_datetime("not-a-date", "%Y-%m-%d") == "Unknown"
