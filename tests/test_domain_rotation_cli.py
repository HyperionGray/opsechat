"""
Tests for domain_rotation_cli persistence helpers.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from domain_manager import DomainRotationManager
from domain_rotation_cli import (
    deserialize_domain_record,
    save_manager_state,
    serialize_domain_record,
)


def test_domain_record_serialize_deserialize_roundtrip():
    """Serialized records should load back into runtime datetime objects."""
    now = datetime.now()
    record = {
        "domain": "roundtrip.xyz",
        "price": 2.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=365),
    }

    stored = serialize_domain_record(record)
    loaded = deserialize_domain_record(stored)

    assert stored is not None
    assert loaded is not None
    assert loaded["domain"] == "roundtrip.xyz"
    assert isinstance(loaded["purchased_at"], datetime)
    assert isinstance(loaded["expires_at"], datetime)


def test_save_manager_state_serializes_owned_domains():
    """save_manager_state should write JSON-safe domain objects."""
    now = datetime.now()
    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 2.99
    manager.active_domain = "saved.xyz"
    manager.owned_domains = [
        {
            "domain": "saved.xyz",
            "price": "2.99",
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]
    config = {}

    with patch("domain_rotation_cli.save_config") as mocked_save:
        save_manager_state(manager, config)

    mocked_save.assert_called_once()
    assert config["current_spending"] == 2.99
    assert config["active_domain"] == "saved.xyz"
    assert isinstance(config["owned_domains"], list)
    assert config["owned_domains"][0]["domain"] == "saved.xyz"
    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(config["owned_domains"][0]["expires_at"], str)

