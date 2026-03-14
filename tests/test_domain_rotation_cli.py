"""
Tests for domain_rotation_cli state persistence and budget rollover behavior.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def _previous_month_key():
    now = datetime.utcnow()
    if now.month == 1:
        return f"{now.year - 1}-12"
    return f"{now.year}-{now.month - 1:02d}"


def test_save_manager_state_serializes_datetime_values(monkeypatch, tmp_path):
    """Saving manager state should write JSON-safe datetime strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(api_client=Mock())
    purchased_at = datetime(2026, 3, 14, 12, 30, 0)
    expires_at = purchased_at + timedelta(days=365)
    manager.owned_domains = [{
        "domain": "example.xyz",
        "price": 1.99,
        "purchased_at": purchased_at,
        "expires_at": expires_at,
    }]
    manager.current_spending = 1.99
    manager.active_domain = "example.xyz"

    config = {
        "api_key": "test-key",
        "api_secret": "test-secret",
        "monthly_budget": 50.0,
    }

    cli.save_manager_state(manager, config)

    with open(config_path, "r", encoding="utf-8") as handle:
        saved = json.load(handle)

    owned = saved["owned_domains"][0]
    assert owned["purchased_at"].startswith("2026-03-14T12:30:00")
    assert owned["expires_at"].startswith("2027-03-14T12:30:00")
    assert saved["budget_month"] == cli._current_month_key()


def test_get_manager_resets_monthly_spending_and_deserializes_dates(monkeypatch, tmp_path):
    """Loading manager should reset spending on month rollover and parse datetimes."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    class DummyClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    monkeypatch.setattr(cli, "PorkbunAPIClient", DummyClient)

    initial = {
        "api_key": "test-key",
        "api_secret": "test-secret",
        "monthly_budget": 75.0,
        "current_spending": 12.5,
        "budget_month": _previous_month_key(),
        "active_domain": "rotate123.xyz",
        "owned_domains": [{
            "domain": "rotate123.xyz",
            "price": 2.49,
            "purchased_at": "2026-02-01T10:00:00",
            "expires_at": "2027-02-01T10:00:00",
        }],
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(initial, handle)

    manager, _config = cli.get_manager()

    assert manager.current_spending == 0.0
    assert manager.active_domain == "rotate123.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)

    with open(config_path, "r", encoding="utf-8") as handle:
        saved = json.load(handle)

    assert saved["current_spending"] == 0.0
    assert saved["budget_month"] == cli._current_month_key()
