"""
Tests for domain_rotation_cli state persistence helpers.
"""
import json
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetime_fields(monkeypatch):
    """save_manager_state should write JSON-safe domain state."""
    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 2.99
    manager.active_domain = "abc123.xyz"
    manager.owned_domains = [{
        "domain": "abc123.xyz",
        "price": 2.99,
        "purchased_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=365),
    }]

    saved = {}

    def fake_save_config(config):
        saved.update(config)

    monkeypatch.setattr(cli, "save_config", fake_save_config)

    config = {}
    cli.save_manager_state(manager, config)

    assert "manager_state" in config
    assert isinstance(config["manager_state"]["owned_domains"][0]["purchased_at"], str)
    assert isinstance(config["manager_state"]["owned_domains"][0]["expires_at"], str)
    # Must remain JSON-serializable for persisted config files.
    json.dumps(config)
    assert saved["active_domain"] == "abc123.xyz"


def test_get_manager_imports_legacy_top_level_state(monkeypatch):
    """get_manager should preserve backward compatibility with legacy config keys."""
    now_iso = datetime.utcnow().isoformat()
    legacy_config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 15.0,
        "current_spending": 4.0,
        "active_domain": "legacy.xyz",
        "owned_domains": [{
            "domain": "legacy.xyz",
            "price": 4.0,
            "purchased_at": now_iso,
            "expires_at": now_iso,
        }],
    }
    monkeypatch.setattr(cli, "load_config", lambda: legacy_config)

    manager, config = cli.get_manager()

    assert config is legacy_config
    assert manager.active_domain == "legacy.xyz"
    assert manager.current_spending == 4.0
    assert manager.owned_domains[0]["domain"] == "legacy.xyz"
    assert hasattr(manager.owned_domains[0]["purchased_at"], "strftime")
