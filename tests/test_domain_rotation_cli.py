"""
Tests for domain_rotation_cli helpers.
"""
from datetime import datetime, timedelta

from domain_rotation_cli import _deserialize_owned_domains, _serialize_owned_domains


def test_owned_domain_datetime_round_trip():
    """Owned domain timestamps can be persisted and restored."""
    now = datetime(2026, 3, 16, 12, 0, 0)
    domains = [
        {
            "domain": "abc123.xyz",
            "price": 2.99,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    serialized = _serialize_owned_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = _deserialize_owned_domains(serialized)
    assert restored[0]["purchased_at"] == now
    assert restored[0]["expires_at"] == now + timedelta(days=365)
