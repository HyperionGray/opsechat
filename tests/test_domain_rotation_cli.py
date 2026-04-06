"""
Tests for domain_rotation_cli state persistence and date handling.
"""
from datetime import datetime

from domain_manager import DomainRotationManager
import domain_rotation_cli as cli


def test_save_manager_state_serializes_datetimes(monkeypatch):
    """Datetime fields should be JSON-safe ISO strings."""
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.5
    manager.active_domain = "alpha.xyz"
    manager.owned_domains = [{
        "domain": "alpha.xyz",
        "price": 2.5,
        "purchased_at": datetime(2026, 4, 1, 12, 0, 0),
        "expires_at": datetime(2027, 4, 1, 12, 0, 0),
    }]

    captured = {}

    def fake_save_config(config):
        captured["config"] = config

    monkeypatch.setattr(cli, "save_config", fake_save_config)

    config = {}
    cli.save_manager_state(manager, config)

    assert config["current_spending"] == 2.5
    assert config["active_domain"] == "alpha.xyz"
    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(config["owned_domains"][0]["expires_at"], str)
    assert config["owned_domains"][0]["purchased_at"].startswith("2026-04-01T12:00:00")
    assert config["owned_domains"][0]["expires_at"].startswith("2027-04-01T12:00:00")
    assert captured["config"] is config


def test_get_manager_deserializes_iso_datetimes(monkeypatch):
    """Stored ISO datetime strings should be converted back to datetime."""
    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 10.0,
        "current_spending": 3.0,
        "active_domain": "beta.xyz",
        "owned_domains": [{
            "domain": "beta.xyz",
            "price": 3.0,
            "purchased_at": "2026-04-02T10:11:12",
            "expires_at": "2027-04-02T10:11:12",
        }],
    }

    monkeypatch.setattr(cli, "load_config", lambda: config)

    manager, loaded_config = cli.get_manager()

    assert loaded_config is config
    assert manager.active_domain == "beta.xyz"
    assert manager.current_spending == 3.0
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_list_domains_handles_persisted_string_dates(monkeypatch, capsys):
    """list command should display persisted date strings without crashing."""
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.active_domain = "gamma.xyz"
    manager.owned_domains = [{
        "domain": "gamma.xyz",
        "price": 1.99,
        "purchased_at": "2026-04-03T08:00:00",
        "expires_at": "2027-04-03T08:00:00",
    }]

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {}))

    cli.list_domains()
    output = capsys.readouterr().out

    assert "gamma.xyz [ACTIVE]" in output
    assert "Purchased: 2026-04-03 08:00" in output
    assert "Expires: 2027-04-03" in output
