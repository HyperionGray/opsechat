"""
Tests for domain rotation CLI persistence and parsing helpers.
"""
from datetime import datetime

import domain_rotation_cli as cli


def test_parse_tld_list_normalizes_and_deduplicates():
    result = cli._parse_tld_list(" .XYZ,club,xyz,, .Online ")
    assert result == ["xyz", "club", "online"]


def test_serialize_deserialize_owned_domains_round_trip():
    original = [{
        "domain": "abc.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 4, 4, 12, 30, 0),
        "expires_at": datetime(2027, 4, 4, 12, 30, 0),
    }]

    serialized = cli._serialize_owned_domains(original)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = cli._deserialize_owned_domains(serialized)
    assert isinstance(restored[0]["purchased_at"], datetime)
    assert isinstance(restored[0]["expires_at"], datetime)
    assert restored[0]["domain"] == "abc.xyz"
    assert restored[0]["price"] == 2.99


def test_format_timestamp_handles_invalid_and_missing():
    assert cli._format_timestamp("not-a-date", "%Y-%m-%d") == "not-a-date"
    assert cli._format_timestamp(None, "%Y-%m-%d") == "N/A"
