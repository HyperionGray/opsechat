"""
Tests for domain_rotation_cli state persistence and cleanup flows.
"""
import json
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def _write_config(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def test_save_manager_state_serializes_datetime_fields(tmp_path, monkeypatch):
    """CLI state save writes JSON-safe datetime strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 7.25
    manager.active_domain = "example.xyz"
    manager.owned_domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": datetime.now() - timedelta(days=1),
            "expires_at": datetime.now() + timedelta(days=364),
        }
    ]

    config = {"api_key": "pk1_test", "api_secret": "sk1_test", "monthly_budget": 50.0}
    cli.save_manager_state(manager, config)

    with open(config_path) as f:
        saved = json.load(f)

    assert saved["active_domain"] == "example.xyz"
    assert saved["current_spending"] == 7.25
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)


def test_get_manager_imports_state_and_parses_datetimes(tmp_path, monkeypatch):
    """CLI manager load restores datetime fields for domain entries."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    _write_config(
        config_path,
        {
            "api_key": "pk1_test",
            "api_secret": "sk1_test",
            "monthly_budget": 42.0,
            "current_spending": 3.5,
            "active_domain": "valid.xyz",
            "owned_domains": [
                {
                    "domain": "valid.xyz",
                    "price": 1.5,
                    "purchased_at": (datetime.now() - timedelta(days=2)).isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=200)).isoformat(),
                }
            ],
        },
    )

    manager, _config = cli.get_manager()
    assert manager.monthly_budget == 42.0
    assert manager.current_spending == 3.5
    assert manager.active_domain == "valid.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_cleanup_domains_prunes_expired_records_from_saved_state(tmp_path, monkeypatch):
    """CLI cleanup command removes expired entries and persists updated state."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    _write_config(
        config_path,
        {
            "api_key": "pk1_test",
            "api_secret": "sk1_test",
            "monthly_budget": 42.0,
            "current_spending": 3.5,
            "active_domain": "expired.xyz",
            "owned_domains": [
                {
                    "domain": "expired.xyz",
                    "price": 1.0,
                    "purchased_at": (datetime.now() - timedelta(days=10)).isoformat(),
                    "expires_at": (datetime.now() - timedelta(seconds=1)).isoformat(),
                },
                {
                    "domain": "valid.xyz",
                    "price": 1.5,
                    "purchased_at": (datetime.now() - timedelta(days=2)).isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=200)).isoformat(),
                },
            ],
        },
    )

    cli.cleanup_domains()

    with open(config_path) as f:
        saved = json.load(f)

    assert len(saved["owned_domains"]) == 1
    assert saved["owned_domains"][0]["domain"] == "valid.xyz"
    assert saved["active_domain"] is None
