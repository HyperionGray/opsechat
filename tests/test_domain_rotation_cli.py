"""
Tests for domain_rotation_cli state persistence behavior.
"""
import json
from datetime import datetime

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetimes(tmp_path):
    """save_manager_state should emit JSON-safe state."""
    domain_rotation_cli.CONFIG_FILE = tmp_path / "domain_config.json"

    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.5
    manager.active_domain = "persisted.xyz"
    manager.owned_domains = [{
        "domain": "persisted.xyz",
        "price": 2.5,
        "purchased_at": datetime(2026, 1, 1, 10, 0, 0),
        "expires_at": datetime(2027, 1, 1, 10, 0, 0),
    }]

    config = {
        "api_key": "k",
        "api_secret": "s",
        "monthly_budget": 50.0,
    }
    domain_rotation_cli.save_manager_state(manager, config)

    stored = json.loads((tmp_path / "domain_config.json").read_text())
    assert stored["owned_domains"][0]["purchased_at"] == "2026-01-01T10:00:00"
    assert stored["owned_domains"][0]["expires_at"] == "2027-01-01T10:00:00"
    assert stored["active_domain"] == "persisted.xyz"
    assert stored["current_spending"] == 2.5


def test_list_domains_handles_iso_timestamp_state(tmp_path, capsys):
    """list command should render persisted ISO datetime strings."""
    domain_rotation_cli.CONFIG_FILE = tmp_path / "domain_config.json"
    (tmp_path / "domain_config.json").write_text(
        json.dumps(
            {
                "api_key": "k",
                "api_secret": "s",
                "monthly_budget": 50.0,
                "current_spending": 2.5,
                "active_domain": "persisted.xyz",
                "owned_domains": [
                    {
                        "domain": "persisted.xyz",
                        "price": 2.5,
                        "purchased_at": "2026-01-01T10:00:00",
                        "expires_at": "2027-01-01T10:00:00",
                    }
                ],
            }
        )
    )

    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    domain_rotation_cli.PorkbunAPIClient = FakeClient
    domain_rotation_cli.list_domains()
    output = capsys.readouterr().out

    assert "persisted.xyz [ACTIVE]" in output
    assert "Purchased: 2026-01-01 10:00" in output
    assert "Expires: 2027-01-01" in output
