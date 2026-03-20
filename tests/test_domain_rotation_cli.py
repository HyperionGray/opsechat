"""
Tests for domain rotation CLI state serialization.
"""

from datetime import datetime, timedelta

from domain_manager import DomainRotationManager
from domain_rotation_cli import (
    deserialize_owned_domains,
    save_manager_state,
    serialize_owned_domains,
)


def test_serialize_owned_domains_converts_datetime_fields():
    now = datetime(2026, 3, 1, 12, 0, 0)
    owned_domains = [
        {
            "domain": "alpha.xyz",
            "price": 2.0,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    serialized = serialize_owned_domains(owned_domains)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)


def test_deserialize_owned_domains_parses_iso_datetime_fields():
    owned_domains = [
        {
            "domain": "beta.xyz",
            "price": 2.5,
            "purchased_at": "2026-03-01T12:00:00",
            "expires_at": "2027-03-01T12:00:00",
        }
    ]

    deserialized = deserialize_owned_domains(owned_domains)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)


def test_save_manager_state_serializes_datetimes(monkeypatch):
    now = datetime(2026, 3, 1, 12, 0, 0)
    manager = DomainRotationManager()
    manager.current_spending = 3.5
    manager.active_domain = "gamma.xyz"
    manager.owned_domains = [
        {
            "domain": "gamma.xyz",
            "price": 3.5,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    captured = {}

    def fake_save_config(config):
        captured["config"] = config

    monkeypatch.setattr("domain_rotation_cli.save_config", fake_save_config)
    save_manager_state(manager, {})

    saved_owned = captured["config"]["owned_domains"][0]
    assert isinstance(saved_owned["purchased_at"], str)
    assert isinstance(saved_owned["expires_at"], str)
