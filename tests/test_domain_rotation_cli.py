"""
Tests for domain_rotation_cli persistence helpers.
"""
from datetime import datetime

import pytest

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_and_restore_manager_state_with_datetimes(tmp_path, monkeypatch):
    """Manager state should round-trip datetimes through JSON config."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 2.99
    manager.active_domain = "alpha123.xyz"
    manager.owned_domains = [{
        "domain": "alpha123.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 1, 12, 0, 0),
        "expires_at": datetime(2027, 3, 1, 12, 0, 0),
    }]

    config = {
        "api_key": "pk_test_1234",
        "api_secret": "sk_test_5678",
        "monthly_budget": 20.0,
    }
    cli.save_manager_state(manager, config)

    stored = cli.load_config()
    assert isinstance(stored["owned_domains"][0]["purchased_at"], str)
    assert isinstance(stored["owned_domains"][0]["expires_at"], str)

    restored_manager, _ = cli.get_manager()
    restored_record = restored_manager.owned_domains[0]
    assert isinstance(restored_record["purchased_at"], datetime)
    assert isinstance(restored_record["expires_at"], datetime)
    assert restored_manager.active_domain == "alpha123.xyz"


def test_get_manager_exits_when_credentials_missing(tmp_path, monkeypatch):
    """CLI should fail fast when API credentials are missing."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    cli.save_config({"monthly_budget": 5.0})

    with pytest.raises(SystemExit):
        cli.get_manager()
