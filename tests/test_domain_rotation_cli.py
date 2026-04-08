"""
Tests for domain_rotation_cli persistence helpers.
"""

from datetime import datetime

from domain_rotation_cli import deserialize_owned_domains, serialize_owned_domains


def test_serialize_owned_domains_converts_datetimes():
    domains = [
        {
            "domain": "alpha.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 4, 1, 12, 0, 0),
            "expires_at": datetime(2027, 4, 1, 12, 0, 0),
        }
    ]

    serialized = serialize_owned_domains(domains)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)
    assert serialized[0]["domain"] == "alpha.xyz"


def test_deserialize_owned_domains_restores_datetimes():
    domains = [
        {
            "domain": "beta.xyz",
            "price": 2.49,
            "purchased_at": "2026-04-02T08:15:00",
            "expires_at": "2027-04-02T08:15:00",
        }
    ]

    deserialized = deserialize_owned_domains(domains)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["domain"] == "beta.xyz"


def test_deserialize_owned_domains_handles_invalid_datetimes():
    domains = [
        {
            "domain": "gamma.xyz",
            "price": 2.99,
            "purchased_at": "not-a-date",
            "expires_at": "",
        }
    ]

    deserialized = deserialize_owned_domains(domains)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
