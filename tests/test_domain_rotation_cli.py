"""
Tests for domain rotation CLI state handling.
"""

from datetime import datetime, timedelta

import domain_rotation_cli as drc
from domain_manager import DomainRotationManager


def test_save_and_load_manager_state_roundtrip(tmp_path, monkeypatch):
    """Persisted state should keep datetime values across save/load."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(drc, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=20.0)
    now = datetime(2026, 3, 18, 6, 0, 0)
    manager.current_spending = 2.99
    manager.owned_domains = [{
        "domain": "testdomain.xyz",
        "price": 2.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=365),
    }]
    manager.active_domain = "testdomain.xyz"

    config = {
        "api_key": "pk_test_123",
        "api_secret": "sk_test_456",
        "monthly_budget": 20.0,
    }
    drc.save_manager_state(manager, config)

    loaded_config = drc.load_config()
    assert isinstance(loaded_config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(loaded_config["owned_domains"][0]["expires_at"], str)

    loaded_manager, _ = drc.get_manager()
    assert loaded_manager.active_domain == "testdomain.xyz"
    assert isinstance(loaded_manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(loaded_manager.owned_domains[0]["expires_at"], datetime)


def test_list_domains_tolerates_non_iso_timestamps(tmp_path, monkeypatch, capsys):
    """Listing domains should not crash on legacy/non-ISO timestamp strings."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(drc, "CONFIG_FILE", config_file)

    drc.save_config({
        "api_key": "pk_test_123",
        "api_secret": "sk_test_456",
        "monthly_budget": 10.0,
        "current_spending": 1.0,
        "active_domain": "legacy.xyz",
        "owned_domains": [{
            "domain": "legacy.xyz",
            "price": 1.0,
            "purchased_at": "legacy-date-format",
            "expires_at": "legacy-date-format",
        }],
    })

    drc.list_domains()
    output = capsys.readouterr().out
    assert "legacy.xyz" in output
