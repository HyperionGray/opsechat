"""
Tests for domain rotation CLI state serialization helpers.
"""
from datetime import datetime

from domain_rotation_cli import (
    _serialize_domain_record,
    _deserialize_domain_record,
    _format_datetime,
)


def test_serialize_domain_record_converts_datetimes():
    now = datetime(2026, 3, 20, 12, 30, 0)
    record = {
        "domain": "example.xyz",
        "purchased_at": now,
        "expires_at": now,
    }
    
    serialized = _serialize_domain_record(record)
    
    assert serialized["purchased_at"] == now.isoformat()
    assert serialized["expires_at"] == now.isoformat()


def test_deserialize_domain_record_converts_iso_strings():
    record = {
        "domain": "example.xyz",
        "purchased_at": "2026-03-20T12:30:00",
        "expires_at": "2027-03-20T12:30:00",
    }
    
    deserialized = _deserialize_domain_record(record)
    
    assert isinstance(deserialized["purchased_at"], datetime)
    assert isinstance(deserialized["expires_at"], datetime)


def test_format_datetime_supports_iso_strings():
    formatted = _format_datetime("2026-03-20T12:30:00", "%Y-%m-%d")
    assert formatted == "2026-03-20"
