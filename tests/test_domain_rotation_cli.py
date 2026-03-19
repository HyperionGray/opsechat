"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from domain_rotation_cli import (
    _normalize_config,
    _serialize_owned_domains,
    _deserialize_owned_domains,
    save_manager_state,
)


def test_normalize_config_migrates_legacy_porkbun_keys():
    legacy = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 42.0,
    }

    normalized = _normalize_config(legacy)

    assert "registrars" in normalized
    assert "porkbun" in normalized["registrars"]
    assert normalized["registrars"]["porkbun"]["api_key"] == "pk_test"
    assert normalized["registrars"]["porkbun"]["api_secret"] == "sk_test"
    assert normalized["active_provider"] == "porkbun"


def test_owned_domains_datetime_serialization_roundtrip():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    owned_domains = [
        {
            "domain": "test123.xyz",
            "price": 2.99,
            "provider": "porkbun",
            "purchased_at": now,
            "expires_at": now,
        }
    ]

    serialized = _serialize_owned_domains(owned_domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = _deserialize_owned_domains(serialized)
    assert restored[0]["purchased_at"] == now
    assert restored[0]["expires_at"] == now


def test_save_manager_state_serializes_datetimes():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    manager = Mock()
    manager.current_spending = 5.0
    manager.owned_domains = [
        {
            "domain": "test123.xyz",
            "price": 2.99,
            "provider": "namecheap",
            "purchased_at": now,
            "expires_at": now,
        }
    ]
    manager.active_domain = "test123.xyz"
    manager.get_active_provider.return_value = "namecheap"

    config = {}
    with patch("domain_rotation_cli.save_config") as mock_save:
        save_manager_state(manager, config)

    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(config["owned_domains"][0]["expires_at"], str)
    assert config["active_provider"] == "namecheap"
    mock_save.assert_called_once()
