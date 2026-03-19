"""
Tests for domain rotation CLI state persistence.
"""
from datetime import datetime

import domain_manager
import domain_rotation_cli
from domain_manager import DomainRotationManager


class _DummyPorkbunClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain):
        return {"available": False}

    def purchase_domain(self, domain, years=1):
        return {"success": False}

    def get_pricing(self, tld):
        return {}


def test_save_manager_state_serializes_datetimes_and_migrates_keys(tmp_path, monkeypatch):
    """CLI should persist JSON-safe structured state and remove legacy keys."""
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", tmp_path / "domain_config.json")

    manager = DomainRotationManager(monthly_budget=25.0)
    manager.current_spending = 3.5
    manager.active_domain = "alpha123.xyz"
    manager.owned_domains = [{
        "domain": "alpha123.xyz",
        "price": 1.99,
        "purchased_at": datetime(2026, 3, 14, 8, 0, 0),
        "expires_at": datetime(2027, 3, 14, 8, 0, 0)
    }]

    config = {
        "api_key": "pk_example",
        "api_secret": "sk_example",
        "current_spending": 999,
        "owned_domains": [],
        "active_domain": "legacy.xyz"
    }
    domain_rotation_cli.save_manager_state(manager, config)
    saved = domain_rotation_cli.load_config()

    assert "state" in saved
    assert "current_spending" not in saved
    assert "owned_domains" not in saved
    assert "active_domain" not in saved
    assert saved["state"]["active_domain"] == "alpha123.xyz"
    assert isinstance(saved["state"]["owned_domains"][0]["purchased_at"], str)


def test_get_manager_loads_legacy_flat_state(tmp_path, monkeypatch):
    """CLI should load old flat config fields for backward compatibility."""
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", tmp_path / "domain_config.json")
    monkeypatch.setattr(domain_manager, "PorkbunAPIClient", _DummyPorkbunClient)

    legacy_config = {
        "api_key": "pk_legacy",
        "api_secret": "sk_legacy",
        "monthly_budget": 12.0,
        "current_spending": 2.0,
        "active_domain": "legacy123.xyz",
        "owned_domains": [{
            "domain": "legacy123.xyz",
            "price": 2.0,
            "purchased_at": "2026-03-14T10:00:00",
            "expires_at": "2027-03-14T10:00:00"
        }]
    }
    domain_rotation_cli.save_config(legacy_config)

    manager, _config = domain_rotation_cli.get_manager()
    assert manager.monthly_budget == 12.0
    assert manager.current_spending == 2.0
    assert manager.active_domain == "legacy123.xyz"
    assert len(manager.owned_domains) == 1
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
