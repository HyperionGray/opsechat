"""
Tests for domain rotation CLI state helpers.
"""
from datetime import datetime

from domain_rotation_cli import _serialize_domain_record, _deserialize_domain_record


def test_domain_record_serialization_round_trip():
    """Datetime fields should be JSON-safe and recoverable."""
    original = {
        "domain": "example.xyz",
        "price": 1.99,
        "provider": "porkbun",
        "purchased_at": datetime(2026, 3, 16, 12, 0, 0),
        "expires_at": datetime(2027, 3, 16, 12, 0, 0),
    }

    serialized = _serialize_domain_record(original)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    restored = _deserialize_domain_record(serialized)
    assert isinstance(restored["purchased_at"], datetime)
    assert isinstance(restored["expires_at"], datetime)


def test_domain_record_deserialize_keeps_unknown_timestamp():
    """Non-ISO timestamps should be preserved instead of crashing."""
    record = {
        "domain": "example.xyz",
        "price": 2.49,
        "purchased_at": "not-a-timestamp",
    }
    restored = _deserialize_domain_record(record)
    assert restored["purchased_at"] == "not-a-timestamp"
