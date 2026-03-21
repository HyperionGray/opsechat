"""
Tests for domain_rotation_cli persistence helpers.
"""
from datetime import datetime, timedelta

from domain_rotation_cli import (
    _deserialize_domain_record,
    _serialize_domain_record,
    get_manager,
    save_config,
)


def test_serialize_deserialize_domain_record_round_trip():
    now = datetime.now()
    record = {
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=365),
    }

    serialized = _serialize_domain_record(record)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    deserialized = _deserialize_domain_record(serialized)
    assert isinstance(deserialized["purchased_at"], datetime)
    assert isinstance(deserialized["expires_at"], datetime)
    assert deserialized["domain"] == "example.xyz"


def test_get_manager_deserializes_owned_domains(monkeypatch, tmp_path):
    from domain_rotation_cli import CONFIG_FILE as original_config_file
    import domain_rotation_cli

    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    save_config({
        "api_key": "pk1_testing_key",
        "api_secret": "sk1_testing_secret",
        "monthly_budget": 30.0,
        "current_spending": 2.99,
        "active_domain": "example.xyz",
        "owned_domains": [{
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
        }],
    })

    manager, _ = get_manager()
    assert len(manager.owned_domains) == 1
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)
    assert manager.active_domain == "example.xyz"

    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", original_config_file)
