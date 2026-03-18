"""
Tests for domain_rotation_cli.py state persistence helpers.
"""
import json
from datetime import datetime, timedelta

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """Datetime fields should be saved as ISO strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    now = datetime(2026, 3, 18, 12, 0, 0)
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.5
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 2.5,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    config = {"api_key": "key", "api_secret": "secret", "monthly_budget": 50.0}
    domain_rotation_cli.save_manager_state(manager, config)

    saved_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(saved_config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved_config["owned_domains"][0]["expires_at"], str)
    assert saved_config["current_spending"] == 2.5
    assert saved_config["active_domain"] == "active.xyz"


def test_get_manager_deserializes_owned_domain_state(tmp_path, monkeypatch):
    """Serialized state should hydrate back to datetime/float values."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 20.0,
        "current_spending": "3.25",
        "active_domain": "test123.xyz",
        "owned_domains": [
            {
                "domain": "test123.xyz",
                "price": "1.25",
                "purchased_at": "2026-03-01T10:00:00",
                "expires_at": "2027-03-01T10:00:00",
            }
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    manager, _ = domain_rotation_cli.get_manager()

    domains = manager.get_owned_domains()
    assert manager.current_spending == 3.25
    assert len(domains) == 1
    assert domains[0]["price"] == 1.25
    assert isinstance(domains[0]["purchased_at"], datetime)
    assert isinstance(domains[0]["expires_at"], datetime)


def test_cleanup_domains_command_persists_pruned_state(tmp_path, monkeypatch):
    """Cleanup command should remove expired records and save the result."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 20.0,
        "current_spending": 3.25,
        "active_domain": "expired.xyz",
        "owned_domains": [
            {
                "domain": "expired.xyz",
                "price": 1.0,
                "purchased_at": (now - timedelta(days=370)).isoformat(),
                "expires_at": (now - timedelta(days=1)).isoformat(),
            },
            {
                "domain": "active.xyz",
                "price": 2.25,
                "purchased_at": (now - timedelta(days=10)).isoformat(),
                "expires_at": (now + timedelta(days=355)).isoformat(),
            },
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    domain_rotation_cli.cleanup_domains()

    updated_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert len(updated_config["owned_domains"]) == 1
    assert updated_config["owned_domains"][0]["domain"] == "active.xyz"
    assert updated_config["active_domain"] == "active.xyz"
