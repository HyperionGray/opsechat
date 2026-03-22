"""Tests for domain_rotation_cli persistence helpers."""

from datetime import datetime

from domain_rotation_cli import _serialize_owned_domains, _deserialize_owned_domains


def test_owned_domain_serialization_round_trip():
    original = [
        {
            "domain": "example.xyz",
            "price": 2.5,
            "provider": "porkbun",
            "purchased_at": datetime(2026, 3, 20, 12, 30, 0),
            "expires_at": datetime(2027, 3, 20, 12, 30, 0),
        }
    ]

    serialized = _serialize_owned_domains(original)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    hydrated = _deserialize_owned_domains(serialized)
    assert hydrated[0]["domain"] == "example.xyz"
    assert hydrated[0]["provider"] == "porkbun"
    assert hydrated[0]["purchased_at"] == datetime(2026, 3, 20, 12, 30, 0)
    assert hydrated[0]["expires_at"] == datetime(2027, 3, 20, 12, 30, 0)
