from datetime import datetime

from domain_rotation_cli import (
    _deserialize_owned_domains,
    _parse_datetime,
    _serialize_owned_domains,
)


def test_serialize_owned_domains_converts_datetimes():
    owned = [
        {
            "domain": "example.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 3, 1, 12, 30, 0),
            "expires_at": datetime(2027, 3, 1, 12, 30, 0),
        }
    ]

    serialized = _serialize_owned_domains(owned)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)
    assert serialized[0]["purchased_at"].startswith("2026-03-01T12:30:00")


def test_deserialize_owned_domains_restores_datetimes():
    owned = [
        {
            "domain": "example.xyz",
            "price": 1.99,
            "purchased_at": "2026-03-01T12:30:00",
            "expires_at": "2027-03-01T12:30:00",
        }
    ]

    deserialized = _deserialize_owned_domains(owned)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["domain"] == "example.xyz"


def test_parse_datetime_handles_invalid_value():
    assert _parse_datetime("not-a-datetime") is None
