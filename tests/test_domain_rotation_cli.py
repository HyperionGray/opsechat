"""
Tests for domain_rotation_cli persistence helpers.
"""

from datetime import datetime

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_format_datetime_value_handles_iso_strings():
    """CLI formatter should render ISO strings into expected output format."""
    formatted = domain_rotation_cli._format_datetime_value(
        "2026-03-04T05:06:07", "%Y-%m-%d"
    )
    assert formatted == "2026-03-04"


def test_save_manager_state_serializes_datetimes(monkeypatch):
    """Saving manager state should produce JSON-serializable timestamp strings."""
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.5
    manager.active_domain = "example.xyz"
    manager.owned_domains = [
        {
            "domain": "example.xyz",
            "price": 2.5,
            "purchased_at": datetime(2026, 3, 4, 5, 6, 7),
            "expires_at": datetime(2027, 3, 4, 5, 6, 7),
        }
    ]

    config = {"api_key": "pk_test", "api_secret": "sk_test", "monthly_budget": 50.0}
    monkeypatch.setattr(domain_rotation_cli, "save_config", lambda _: None)
    domain_rotation_cli.save_manager_state(manager, config)

    assert config["current_spending"] == 2.5
    assert config["active_domain"] == "example.xyz"
    assert config["owned_domains"][0]["purchased_at"] == "2026-03-04T05:06:07"
    assert config["owned_domains"][0]["expires_at"] == "2027-03-04T05:06:07"
