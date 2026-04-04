"""
Tests for domain_rotation_cli state handling and command dispatch.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

import domain_rotation_cli as cli


def test_serialize_deserialize_domain_record_roundtrip():
    record = {
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
        "expires_at": datetime(2027, 1, 2, 3, 4, 5),
    }

    serialized = cli._serialize_domain_record(record)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    deserialized = cli._deserialize_domain_record(serialized)
    assert isinstance(deserialized["purchased_at"], datetime)
    assert isinstance(deserialized["expires_at"], datetime)
    assert deserialized["domain"] == "example.xyz"


def test_load_manager_from_saved_config_deserializes_datetimes(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    saved = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 25.0,
        "current_spending": "4.5",
        "active_domain": "active.xyz",
        "owned_domains": [
            {
                "domain": "active.xyz",
                "price": 2.99,
                "purchased_at": "2026-02-03T04:05:06",
                "expires_at": "2027-02-03T04:05:06",
            }
        ],
    }
    config_path.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager, _config = cli.get_manager()
    assert manager.current_spending == pytest.approx(4.5)
    assert manager.active_domain == "active.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_save_manager_state_json_safe(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    class DummyManager:
        current_spending = 3.14
        active_domain = "safe.xyz"
        owned_domains = [
            {
                "domain": "safe.xyz",
                "price": 1.99,
                "purchased_at": datetime(2026, 3, 4, 5, 6, 7),
                "expires_at": datetime(2027, 3, 4, 5, 6, 7),
            }
        ]

    cli.save_manager_state(DummyManager(), {})
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["active_domain"] == "safe.xyz"
    assert isinstance(persisted["owned_domains"][0]["purchased_at"], str)
    assert isinstance(persisted["owned_domains"][0]["expires_at"], str)


def test_run_command_rejects_unsupported():
    with pytest.raises(ValueError, match="Unsupported command"):
        cli.run_command("does-not-exist")
