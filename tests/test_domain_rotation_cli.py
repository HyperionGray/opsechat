"""
Tests for domain_rotation_cli helper behavior.
"""
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import PorkbunAPIClient


def test_normalize_config_backward_compatibility_keys():
    """Legacy config keys should map to modern provider-specific keys."""
    normalized = cli.normalize_config(
        {
            "api_key": "legacy_key",
            "api_secret": "legacy_secret",
        }
    )

    assert normalized["porkbun_api_key"] == "legacy_key"
    assert normalized["porkbun_api_secret"] == "legacy_secret"
    assert normalized["provider"] == "porkbun"


def test_serialize_deserialize_domain_records_roundtrip():
    """Datetime values should remain usable after persistence transforms."""
    records = [
        {
            "domain": "abc.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 3, 20, 6, 0, 0),
            "expires_at": datetime(2027, 3, 20, 6, 0, 0),
        }
    ]

    serialized = cli.serialize_domain_records(records)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = cli.deserialize_domain_records(serialized)
    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)


def test_build_clients_uses_porkbun_when_available():
    """Auto mode should include configured Porkbun client."""
    config = cli.normalize_config(
        {
            "provider": "auto",
            "porkbun_api_key": "pk",
            "porkbun_api_secret": "sk",
        }
    )

    clients, provider = cli._build_clients(config)
    assert provider == "auto"
    assert len(clients) == 1
    assert isinstance(clients[0], PorkbunAPIClient)
