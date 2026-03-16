"""
Tests for domain_rotation_cli helpers.
"""
from datetime import datetime

from domain_rotation_cli import deserialize_owned_domains, serialize_owned_domains


def test_serialize_owned_domains_converts_datetimes():
    domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 1, 1, 12, 0, 0),
            "expires_at": datetime(2027, 1, 1, 12, 0, 0),
        }
    ]

    serialized = serialize_owned_domains(domains)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)


def test_deserialize_owned_domains_parses_iso_timestamps():
    domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": "2026-01-01T12:00:00",
            "expires_at": "2027-01-01T12:00:00",
        }
    ]

    parsed = deserialize_owned_domains(domains)

    assert isinstance(parsed[0]["purchased_at"], datetime)
    assert isinstance(parsed[0]["expires_at"], datetime)


def test_deserialize_owned_domains_preserves_invalid_timestamp():
    domains = [
        {
            "domain": "example.xyz",
            "purchased_at": "not-a-timestamp",
            "expires_at": "2027-01-01T12:00:00",
        }
    ]

    parsed = deserialize_owned_domains(domains)

    assert parsed[0]["purchased_at"] == "not-a-timestamp"
    assert isinstance(parsed[0]["expires_at"], datetime)
