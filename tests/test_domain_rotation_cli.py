"""
Tests for domain rotation CLI state helpers.
"""
from datetime import datetime

from domain_rotation_cli import (
    _serialize_domains,
    _deserialize_domains,
    _format_domain_datetime,
)


def test_serialize_and_deserialize_domains_roundtrip():
    """CLI state helpers should preserve domain metadata safely."""
    now = datetime(2026, 3, 17, 12, 0, 0)
    domains = [{
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": now,
        "expires_at": now,
    }]

    serialized = _serialize_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = _deserialize_domains(serialized)
    assert restored[0]["domain"] == "example.xyz"
    assert isinstance(restored[0]["purchased_at"], datetime)
    assert isinstance(restored[0]["expires_at"], datetime)


def test_format_domain_datetime_invalid_value():
    """Invalid stored datetime should fail closed to None."""
    assert _format_domain_datetime("invalid-date-value") is None
