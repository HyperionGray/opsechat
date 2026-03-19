"""
Tests for domain rotation CLI persistence and non-interactive rotation behavior.
"""

import json
from datetime import datetime
from unittest.mock import Mock

import pytest

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(monkeypatch, tmp_path):
    """save_manager_state should persist datetime fields as ISO strings."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 2.99
    manager.active_domain = "alpha123.xyz"
    manager.owned_domains = [
        {
            "domain": "alpha123.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 3, 19, 12, 0, 0),
            "expires_at": datetime(2027, 3, 19, 12, 0, 0),
        }
    ]

    domain_rotation_cli.save_manager_state(manager, {})

    with config_file.open("r", encoding="utf-8") as handle:
        saved = json.load(handle)

    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)
    assert saved["owned_domains"][0]["purchased_at"].startswith("2026-03-19T12:00:00")


def test_get_manager_deserializes_owned_domain_datetimes(monkeypatch, tmp_path):
    """get_manager should restore owned domain datetime fields from JSON state."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_file)

    config_data = {
        "api_key": "key123",
        "api_secret": "secret123",
        "monthly_budget": 50.0,
        "current_spending": 1.99,
        "active_domain": "beta456.xyz",
        "owned_domains": [
            {
                "domain": "beta456.xyz",
                "price": 1.99,
                "purchased_at": "2026-03-01T08:00:00",
                "expires_at": "2027-03-01T08:00:00",
            }
        ],
    }
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    manager, loaded_config = domain_rotation_cli.get_manager()

    assert loaded_config["active_domain"] == "beta456.xyz"
    assert manager.current_spending == 1.99
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_rotate_domain_auto_confirm_skips_prompt(monkeypatch):
    """rotate_domain(auto_confirm=True) should not call input()."""
    mock_manager = Mock()
    mock_manager.get_budget_status.return_value = {
        "monthly_budget": 50.0,
        "current_spending": 0.0,
        "remaining": 50.0,
        "domains_owned": 0,
    }
    mock_manager.find_cheap_available_domain.return_value = {
        "domain": "gamma789.xyz",
        "price": 2.49,
    }
    mock_manager.purchase_domain_if_budget_allows.return_value = True

    save_state_spy = Mock()
    monkeypatch.setattr(domain_rotation_cli, "get_manager", lambda: (mock_manager, {}))
    monkeypatch.setattr(domain_rotation_cli, "save_manager_state", save_state_spy)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: pytest.fail("input() should not be called"))

    domain_rotation_cli.rotate_domain(auto_confirm=True, max_price=4.0, attempts=3)

    mock_manager.find_cheap_available_domain.assert_called_once_with(max_price=4.0, max_attempts=3)
    mock_manager.purchase_domain_if_budget_allows.assert_called_once_with("gamma789.xyz", 2.49)
    assert save_state_spy.called
