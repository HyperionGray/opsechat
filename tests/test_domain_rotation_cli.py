"""
Tests for domain_rotation_cli state serialization helpers.
"""
from datetime import datetime

from domain_rotation_cli import _serialize_owned_domains, _deserialize_owned_domains


def test_owned_domain_state_roundtrip_datetime_fields():
    """CLI state should round-trip datetime fields through JSON-safe structures."""
    original = [{
        "domain": "roundtrip.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 10, 9, 30, 0),
        "expires_at": datetime(2027, 3, 10, 9, 30, 0),
    }]

    serialized = _serialize_owned_domains(original)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = _deserialize_owned_domains(serialized)
    assert restored[0]["domain"] == "roundtrip.xyz"
    assert restored[0]["price"] == 2.99
    assert restored[0]["purchased_at"] == datetime(2026, 3, 10, 9, 30, 0)
    assert restored[0]["expires_at"] == datetime(2027, 3, 10, 9, 30, 0)


def test_deserialize_tolerates_invalid_dates():
    """Invalid date values in old config should not crash deserialization."""
    restored = _deserialize_owned_domains([{
        "domain": "legacy.xyz",
        "price": "1.25",
        "purchased_at": "not-a-date",
        "expires_at": None,
    }])

    assert restored[0]["domain"] == "legacy.xyz"
    assert restored[0]["price"] == "1.25"
    assert restored[0]["purchased_at"] == "not-a-date"
    assert restored[0]["expires_at"] is None
