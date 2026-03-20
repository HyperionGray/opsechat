"""
Tests for domain_rotation_cli state persistence helpers.
"""
import datetime
import json
from pathlib import Path
from unittest.mock import patch

from domain_manager import DomainRotationManager
import domain_rotation_cli as cli


def _read_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_save_manager_state_writes_domain_state(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 3.25
    manager.active_domain = "persisted.xyz"
    manager.owned_domains = [{
        "domain": "persisted.xyz",
        "price": 3.25,
        "purchased_at": datetime.datetime(2026, 3, 1, 8, 0, 0),
        "expires_at": datetime.datetime(2027, 3, 1, 8, 0, 0),
    }]

    config = {"api_key": "key", "api_secret": "secret", "monthly_budget": 50.0}
    cli.save_manager_state(manager, config)

    saved = _read_json(config_file)
    assert "domain_state" in saved
    assert saved["domain_state"]["active_domain"] == "persisted.xyz"
    assert isinstance(
        saved["domain_state"]["owned_domains"][0]["purchased_at"], str
    )
    assert saved["current_spending"] == 3.25


def test_get_manager_loads_legacy_state(tmp_path, monkeypatch):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    config_data = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 75.0,
        "current_spending": "$5.10",
        "active_domain": "legacy.xyz",
        "owned_domains": [{
            "domain": "legacy.xyz",
            "price": "5.10",
            "purchased_at": "2026-03-01T12:30:00",
            "expires_at": "2027-03-01T12:30:00",
        }],
    }
    with open(config_file, "w", encoding="utf-8") as handle:
        json.dump(config_data, handle)

    with patch("domain_rotation_cli.PorkbunAPIClient"):
        manager, loaded_config = cli.get_manager()

    assert loaded_config["api_key"] == "key"
    assert manager.current_spending == 5.1
    assert manager.active_domain == "legacy.xyz"
    assert len(manager.owned_domains) == 1
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime.datetime)


def test_format_datetime_handles_invalid_values():
    assert cli._format_datetime("2026-03-01T10:00:00", "%Y-%m-%d") == "2026-03-01"
    assert cli._format_datetime("not-a-date", "%Y-%m-%d") == "unknown"
    assert cli._format_datetime(None, "%Y-%m-%d") == "unknown"
