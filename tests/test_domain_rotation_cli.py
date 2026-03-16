"""
Tests for domain_rotation_cli helper behavior.
"""

from datetime import datetime

from domain_rotation_cli import (
    _deserialize_owned_domains,
    _format_dt,
    _serialize_owned_domains,
)


def test_serialize_owned_domains_converts_datetimes():
    owned_domains = [
        {
            "domain": "example.xyz",
            "purchased_at": datetime(2026, 3, 1, 12, 30, 0),
            "expires_at": datetime(2027, 3, 1, 12, 30, 0),
        }
    ]

    serialized = _serialize_owned_domains(owned_domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)
    assert "2026-03-01T12:30:00" in serialized[0]["purchased_at"]


def test_deserialize_owned_domains_parses_iso_values():
    owned_domains = [
        {
            "domain": "example.xyz",
            "purchased_at": "2026-03-01T12:30:00",
            "expires_at": "2027-03-01T12:30:00",
        }
    ]

    hydrated = _deserialize_owned_domains(owned_domains)
    assert isinstance(hydrated[0]["purchased_at"], datetime)
    assert isinstance(hydrated[0]["expires_at"], datetime)


def test_format_dt_handles_strings_and_datetimes():
    dt_value = datetime(2026, 3, 1, 9, 45, 0)
    assert _format_dt(dt_value) == "2026-03-01 09:45"
    assert _format_dt("2026-03-01T09:45:00") == "2026-03-01 09:45"
    assert _format_dt("not-a-date") == "not-a-date"
