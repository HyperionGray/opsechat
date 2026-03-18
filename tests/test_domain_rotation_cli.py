"""
Tests for domain_rotation_cli state persistence helpers.
"""
import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """save_manager_state should persist JSON-safe domain records."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=30.0)
    manager.current_spending = 2.99
    manager.active_domain = "saved.xyz"
    manager.owned_domains = [{
        "domain": "saved.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 18, 9, 0, 0),
        "expires_at": datetime(2027, 3, 18, 9, 0, 0),
    }]

    cli.save_manager_state(manager, {"api_key": "pk1_test", "api_secret": "sk1_test"})

    with open(config_file, "r", encoding="utf-8") as handle:
        persisted = json.load(handle)

    assert persisted["state"]["active_domain"] == "saved.xyz"
    assert isinstance(persisted["state"]["owned_domains"][0]["purchased_at"], str)
    assert isinstance(persisted["state"]["owned_domains"][0]["expires_at"], str)


def test_get_manager_loads_legacy_state_format(tmp_path, monkeypatch):
    """get_manager should support legacy top-level state keys."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    legacy_config = {
        "api_key": "pk1_test",
        "api_secret": "sk1_test",
        "monthly_budget": 50.0,
        "current_spending": 5.25,
        "active_domain": "legacy.xyz",
        "owned_domains": [{
            "domain": "legacy.xyz",
            "price": 2.99,
            "purchased_at": "2026-03-01T12:00:00",
            "expires_at": "2027-03-01T12:00:00",
        }],
    }
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as handle:
        json.dump(legacy_config, handle)

    manager, _ = cli.get_manager()
    assert manager.active_domain == "legacy.xyz"
    assert manager.current_spending == 5.25
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
