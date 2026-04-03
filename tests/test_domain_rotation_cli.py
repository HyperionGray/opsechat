"""
Tests for domain_rotation_cli persistence and cleanup behavior.
"""

from datetime import datetime, timedelta

import domain_rotation_cli as cli


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """save_manager_state should write JSON-safe state values."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = cli.DomainRotationManager(monthly_budget=25.0)
    now = datetime.now()
    manager.current_spending = 3.5
    manager.active_domain = "active.xyz"
    manager.owned_domains = [{
        "domain": "active.xyz",
        "price": 1.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=10),
    }]

    cli.save_manager_state(manager, {"api_key": "k", "api_secret": "s", "monthly_budget": 25.0})
    stored = cli.load_config()

    assert stored["active_domain"] == "active.xyz"
    assert isinstance(stored["owned_domains"][0]["purchased_at"], str)
    assert isinstance(stored["owned_domains"][0]["expires_at"], str)


def test_get_manager_loads_state_dates(tmp_path, monkeypatch):
    """get_manager should hydrate datetime fields from config."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    cli.save_config(
        {
            "api_key": "k",
            "api_secret": "s",
            "monthly_budget": 30.0,
            "current_spending": 5.0,
            "active_domain": "current.xyz",
            "owned_domains": [
                {
                    "domain": "current.xyz",
                    "price": "2.5",
                    "purchased_at": now.isoformat(),
                    "expires_at": (now + timedelta(days=20)).isoformat(),
                }
            ],
        }
    )

    manager, _config = cli.get_manager()

    assert manager.current_spending == 5.0
    assert manager.active_domain == "current.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)

