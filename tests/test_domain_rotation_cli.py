"""
Tests for domain_rotation_cli persistence helpers.
"""
import json
from datetime import datetime

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """save_manager_state should write JSON-safe datetime strings."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=30.0)
    now = datetime(2026, 1, 2, 3, 4, 5)
    manager.current_spending = 4.5
    manager.active_domain = "example.xyz"
    manager.owned_domains = [{
        "domain": "example.xyz",
        "price": 1.99,
        "purchased_at": now,
        "expires_at": now,
    }]

    config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
    }
    domain_rotation_cli.save_manager_state(manager, config)

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert saved["active_domain"] == "example.xyz"
    assert saved["monthly_budget"] == 30.0


def test_get_manager_loads_persisted_state(tmp_path, monkeypatch):
    """get_manager should hydrate owned domain datetimes from config."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_file)

    config_payload = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 12.0,
        "current_spending": 2.5,
        "active_domain": "active.xyz",
        "owned_domains": [{
            "domain": "active.xyz",
            "price": "1.49",
            "purchased_at": "2026-01-02T03:04:05",
            "expires_at": "2027-01-02T03:04:05",
        }],
    }
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_payload), encoding="utf-8")

    manager, _ = domain_rotation_cli.get_manager()

    assert manager.monthly_budget == 12.0
    assert manager.current_spending == 2.5
    assert manager.active_domain == "active.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
