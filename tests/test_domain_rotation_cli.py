"""
Tests for domain_rotation_cli persistence helpers.
"""
from datetime import datetime
import json
from types import SimpleNamespace

import domain_rotation_cli as cli


def test_domain_entry_serialization_round_trip():
    """Datetime fields should survive save/load conversions."""
    original = {
        "domain": "example.xyz",
        "price": 1.99,
        "provider": "porkbun",
        "purchased_at": datetime(2026, 3, 1, 10, 0, 0),
        "expires_at": datetime(2027, 3, 1, 10, 0, 0),
    }

    serialized = cli._serialize_domain_entry(original)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    restored = cli._deserialize_domain_entry(serialized)
    assert restored["purchased_at"] == original["purchased_at"]
    assert restored["expires_at"] == original["expires_at"]


def test_save_manager_state_serializes_owned_domains(tmp_path, monkeypatch):
    """Saving manager state should produce JSON-safe domain records."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = SimpleNamespace(
        current_spending=2.5,
        active_domain="burner-test.xyz",
        owned_domains=[
            {
                "domain": "burner-test.xyz",
                "price": 2.5,
                "provider": "namecheap",
                "purchased_at": datetime(2026, 3, 1, 12, 0, 0),
                "expires_at": datetime(2027, 3, 1, 12, 0, 0),
            }
        ],
    )
    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 50.0,
    }

    cli.save_manager_state(manager, config)

    raw = json.loads(config_file.read_text())
    assert raw["current_spending"] == 2.5
    assert raw["active_domain"] == "burner-test.xyz"
    assert isinstance(raw["owned_domains"][0]["purchased_at"], str)
