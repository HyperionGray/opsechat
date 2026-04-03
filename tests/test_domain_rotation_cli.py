"""
Tests for domain_rotation_cli persistence behavior.
"""
import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_serialize_deserialize_owned_domains_round_trip():
    owned_domains = [
        {
            "domain": "alpha123.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 3, 10, 11, 30, 0),
            "expires_at": datetime(2027, 3, 10, 11, 30, 0),
        }
    ]

    serialized = cli._serialize_owned_domains(owned_domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = cli._deserialize_owned_domains(serialized)
    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["domain"] == "alpha123.xyz"


def test_get_manager_resets_spending_on_month_change(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    config_file.write_text(
        json.dumps(
            {
                "api_key": "test-key",
                "api_secret": "test-secret",
                "monthly_budget": 50.0,
                "current_spending": 9.99,
                "budget_month": "2000-01",
                "owned_domains": [
                    {
                        "domain": "old123.xyz",
                        "price": 0.99,
                        "purchased_at": "2026-02-01T10:15:00",
                        "expires_at": "2027-02-01T10:15:00",
                    }
                ],
                "active_domain": "old123.xyz",
            }
        )
    )

    manager, config = cli.get_manager()

    assert manager.current_spending == 0.0
    assert config["current_spending"] == 0.0
    assert config["budget_month"] == cli._current_budget_month()
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)

    persisted = json.loads(config_file.read_text())
    assert persisted["current_spending"] == 0.0
    assert persisted["budget_month"] == cli._current_budget_month()


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=30.0)
    manager.current_spending = 3.5
    manager.active_domain = "active123.xyz"
    manager.owned_domains = [
        {
            "domain": "active123.xyz",
            "price": 1.25,
            "purchased_at": datetime(2026, 4, 1, 8, 0, 0),
            "expires_at": datetime(2027, 4, 1, 8, 0, 0),
        }
    ]

    cli.save_manager_state(manager, {"api_key": "k", "api_secret": "s"})

    persisted = json.loads(config_file.read_text())
    assert persisted["active_domain"] == "active123.xyz"
    assert persisted["current_spending"] == 3.5
    assert isinstance(persisted["owned_domains"][0]["purchased_at"], str)
    assert isinstance(persisted["owned_domains"][0]["expires_at"], str)
