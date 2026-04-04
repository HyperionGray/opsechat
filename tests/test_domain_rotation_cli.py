"""
Tests for domain_rotation_cli helper behavior.
"""
from datetime import datetime

from domain_rotation_cli import (
    _serialize_domain_records,
    _deserialize_domain_records,
)


class TestDomainRotationCliSerialization:
    def test_serialize_domain_records_converts_datetimes_to_iso(self):
        records = [{
            "domain": "example.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 4, 4, 12, 0, 0),
            "expires_at": datetime(2027, 4, 4, 12, 0, 0),
        }]

        result = _serialize_domain_records(records)

        assert isinstance(result[0]["purchased_at"], str)
        assert isinstance(result[0]["expires_at"], str)
        assert result[0]["purchased_at"].startswith("2026-04-04T12:00:00")

    def test_deserialize_domain_records_converts_iso_to_datetimes(self):
        records = [{
            "domain": "example.xyz",
            "price": 1.99,
            "purchased_at": "2026-04-04T12:00:00",
            "expires_at": "2027-04-04T12:00:00",
        }]

        result = _deserialize_domain_records(records)

        assert isinstance(result[0]["purchased_at"], datetime)
        assert isinstance(result[0]["expires_at"], datetime)

    def test_deserialize_domain_records_keeps_invalid_timestamp_strings(self):
        records = [{
            "domain": "example.xyz",
            "purchased_at": "not-a-date",
            "expires_at": "also-not-a-date",
        }]

        result = _deserialize_domain_records(records)

        assert result[0]["purchased_at"] == "not-a-date"
        assert result[0]["expires_at"] == "also-not-a-date"
