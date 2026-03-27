"""
Tests for domain_rotation_cli persistence helpers.
"""
from datetime import datetime, timedelta

from domain_rotation_cli import _deserialize_owned_domains, _serialize_owned_domains


def test_owned_domains_datetime_roundtrip():
    now = datetime.now()
    domains = [
        {
            "domain": "example.xyz",
            "price": 1.99,
            "years": 1,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    serialized = _serialize_owned_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = _deserialize_owned_domains(serialized)
    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)


def test_deserialize_owned_domains_keeps_invalid_strings():
    domains = [
        {
            "domain": "broken.xyz",
            "price": 2.99,
            "purchased_at": "not-a-datetime",
            "expires_at": "also-not-a-datetime",
        }
    ]

    parsed = _deserialize_owned_domains(domains)
    assert parsed[0]["purchased_at"] == "not-a-datetime"
    assert parsed[0]["expires_at"] == "also-not-a-datetime"
