"""
Tests for domain_rotation_cli helper behavior.
"""
from datetime import datetime

from domain_rotation_cli import deserialize_owned_domains, serialize_owned_domains


def test_serialize_owned_domains_converts_datetime_fields():
    domains = [{
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 20, 12, 30, 0),
        "expires_at": datetime(2027, 3, 20, 12, 30, 0)
    }]

    serialized = serialize_owned_domains(domains)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)
    assert serialized[0]["domain"] == "example.xyz"


def test_deserialize_owned_domains_parses_iso_datetime_fields():
    domains = [{
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": "2026-03-20T12:30:00",
        "expires_at": "2027-03-20T12:30:00"
    }]

    deserialized = deserialize_owned_domains(domains)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["domain"] == "example.xyz"


def test_deserialize_owned_domains_keeps_unparseable_datetime():
    domains = [{
        "domain": "example.xyz",
        "purchased_at": "not-a-date"
    }]

    deserialized = deserialize_owned_domains(domains)
    assert deserialized[0]["purchased_at"] == "not-a-date"
