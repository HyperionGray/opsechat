"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime

from domain_rotation_cli import _format_datetime, _normalize_owned_domains


def test_normalize_owned_domains_serializes_datetimes():
    now = datetime(2026, 3, 1, 10, 30, 0)
    owned_domains = [
        {
            "domain": "abc123.xyz",
            "price": 2.99,
            "purchased_at": now,
            "expires_at": now,
        }
    ]

    normalized = _normalize_owned_domains(owned_domains)

    assert normalized[0]["provider"] == "unknown"
    assert isinstance(normalized[0]["purchased_at"], str)
    assert isinstance(normalized[0]["expires_at"], str)


def test_format_datetime_handles_iso_with_z_suffix():
    value = "2026-03-01T10:30:00Z"
    assert _format_datetime(value, "%Y-%m-%d") == "2026-03-01"


def test_format_datetime_handles_invalid_values():
    assert _format_datetime("not-a-date", "%Y-%m-%d") == "Unknown"
