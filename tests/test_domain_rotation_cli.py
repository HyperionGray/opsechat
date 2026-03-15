"""
Tests for domain_rotation_cli helpers and state persistence.
"""

import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_format_timestamp_supports_datetime_and_string():
    dt_value = datetime(2026, 3, 15, 10, 45, 0)
    assert cli._format_timestamp(dt_value) == "2026-03-15 10:45"
    assert cli._format_timestamp("2026-03-15T10:45:00") == "2026-03-15 10:45"
    assert cli._format_timestamp(None) == "unknown"


def test_save_manager_state_serializes_owned_domain_timestamps(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 1.99
    manager.active_domain = "persisted.xyz"
    manager.owned_domains = [{
        "domain": "persisted.xyz",
        "price": 1.99,
        "purchased_at": datetime(2026, 3, 15, 9, 0, 0),
        "expires_at": datetime(2027, 3, 15, 9, 0, 0),
    }]

    config = {"api_key": "pk1_test", "api_secret": "sk1_test", "monthly_budget": 20.0}
    cli.save_manager_state(manager, config)

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data["owned_domains"][0]["purchased_at"], str)
    assert data["active_domain"] == "persisted.xyz"
    assert data["current_spending"] == 1.99


def test_get_manager_imports_saved_state(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "api_key": "pk1_test",
                "api_secret": "sk1_test",
                "monthly_budget": 15.0,
                "current_spending": 5.0,
                "active_domain": "loaded.xyz",
                "owned_domains": [
                    {
                        "domain": "loaded.xyz",
                        "price": 5.0,
                        "purchased_at": "2026-03-01T12:00:00",
                        "expires_at": "2027-03-01T12:00:00",
                    }
                ],
            },
            f,
            indent=2,
        )

    manager, _ = cli.get_manager()
    assert manager.active_domain == "loaded.xyz"
    assert manager.current_spending == 5.0
    assert manager.owned_domains[0]["domain"] == "loaded.xyz"
