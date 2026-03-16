"""
Tests for domain_rotation_cli.py state handling.
"""

import json
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_domain_datetimes(tmp_path, monkeypatch):
    """CLI save should persist datetimes as JSON-safe strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=10.0)
    now = datetime.now()
    manager.owned_domains = [{
        "domain": "one.xyz",
        "price": 1.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=365),
    }]
    manager.active_domain = "one.xyz"
    manager.current_spending = 1.99

    cli.save_manager_state(manager, {})

    payload = json.loads(config_path.read_text())
    assert payload["state"]["active_domain"] == "one.xyz"
    assert isinstance(payload["state"]["owned_domains"][0]["purchased_at"], str)
    assert isinstance(payload["state"]["owned_domains"][0]["expires_at"], str)


def test_get_manager_imports_legacy_state_without_api(tmp_path, monkeypatch):
    """Legacy config fields should still load and parse correctly."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    legacy_config = {
        "monthly_budget": 50.0,
        "current_spending": 2.99,
        "active_domain": "legacy.xyz",
        "owned_domains": [{
            "domain": "legacy.xyz",
            "price": 2.99,
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
        }],
    }
    config_path.write_text(json.dumps(legacy_config))

    manager, _ = cli.get_manager(require_api=False)
    domains = manager.get_owned_domains()

    assert manager.current_spending == 2.99
    assert manager.active_domain == "legacy.xyz"
    assert len(domains) == 1
    assert isinstance(domains[0]["purchased_at"], datetime)
    assert isinstance(domains[0]["expires_at"], datetime)
