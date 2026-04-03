"""
Tests for domain_rotation_cli persistence helpers.
"""
import os
import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """Saving manager state should write JSON-safe timestamp strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=25.0)
    manager.current_spending = 5.0
    manager.owned_domains = [{
        "domain": "persist.xyz",
        "price": 1.99,
        "purchased_at": datetime(2026, 3, 1, 12, 0, 0),
        "expires_at": datetime(2027, 3, 1, 12, 0, 0),
    }]
    manager.active_domain = "persist.xyz"

    config = {"api_key": "pk_test", "api_secret": "sk_test", "monthly_budget": 25.0}
    cli.save_manager_state(manager, config)

    assert config_path.exists()
    assert oct(os.stat(config_path).st_mode & 0o777) == "0o600"

    data = json.loads(config_path.read_text())
    assert data["active_domain"] == "persist.xyz"
    assert isinstance(data["owned_domains"][0]["purchased_at"], str)
    assert isinstance(data["owned_domains"][0]["expires_at"], str)


def test_format_datetime_handles_iso_strings():
    """Formatting helper should parse and render ISO timestamps."""
    rendered = cli._format_datetime("2027-03-01T12:00:00Z", "%Y-%m-%d")
    assert rendered == "2027-03-01"

