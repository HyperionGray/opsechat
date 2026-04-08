"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime
from unittest.mock import patch

from domain_manager import DomainRotationManager
from domain_rotation_cli import format_timestamp, save_manager_state


def test_format_timestamp_handles_datetime():
    value = datetime(2026, 1, 2, 3, 4, 5)
    assert format_timestamp(value, "%Y-%m-%d %H:%M") == "2026-01-02 03:04"


def test_format_timestamp_handles_iso_string():
    value = "2026-01-02T03:04:05"
    assert format_timestamp(value, "%Y-%m-%d") == "2026-01-02"


def test_save_manager_state_serializes_domains():
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 3.5
    manager.active_domain = "saved-state.xyz"
    manager.owned_domains = [{
        "domain": "saved-state.xyz",
        "price": 3.5,
        "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
        "expires_at": datetime(2027, 1, 2, 3, 4, 5),
    }]

    config = {"api_key": "k", "api_secret": "s", "monthly_budget": 50.0}
    with patch("domain_rotation_cli.save_config") as mock_save:
        save_manager_state(manager, config)
        mock_save.assert_called_once_with(config)

    assert config["current_spending"] == 3.5
    assert config["active_domain"] == "saved-state.xyz"
    assert config["owned_domains"][0]["purchased_at"] == "2026-01-02T03:04:05"
