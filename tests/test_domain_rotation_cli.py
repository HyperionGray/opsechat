"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_format_datetime_handles_none_and_iso():
    """CLI datetime formatter should be resilient to persisted string values."""
    assert domain_rotation_cli._format_datetime(None, "%Y-%m-%d", fallback="n/a") == "n/a"

    iso_value = "2026-03-20T10:20:30"
    assert domain_rotation_cli._format_datetime(iso_value, "%Y-%m-%d") == "2026-03-20"


def test_save_manager_state_serializes_datetime_fields(monkeypatch):
    """Saving manager state should persist datetime fields as ISO strings."""
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 3.99
    manager.active_domain = "example.xyz"
    manager.owned_domains = [{
        "domain": "example.xyz",
        "price": 3.99,
        "purchased_at": datetime(2026, 3, 20, 10, 15, 0),
        "expires_at": datetime(2027, 3, 20, 10, 15, 0),
    }]

    persisted = {}

    def fake_save_config(config):
        persisted.update(config)

    monkeypatch.setattr(domain_rotation_cli, "save_config", fake_save_config)

    config = {"api_key": "k", "api_secret": "s"}
    domain_rotation_cli.save_manager_state(manager, config)

    assert persisted["active_domain"] == "example.xyz"
    assert persisted["current_spending"] == 3.99
    assert persisted["owned_domains"][0]["purchased_at"].startswith("2026-03-20T10:15:00")
