"""
Tests for domain_rotation_cli persistence helpers and list output handling.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import domain_rotation_cli


def test_serialize_domain_record_converts_datetimes():
    record = {
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 19, 15, 0, 0),
        "expires_at": datetime(2027, 3, 19, 15, 0, 0),
    }

    serialized = domain_rotation_cli._serialize_domain_record(record)

    assert serialized["purchased_at"] == "2026-03-19T15:00:00"
    assert serialized["expires_at"] == "2027-03-19T15:00:00"


def test_deserialize_domain_record_parses_iso_timestamps():
    record = {
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": "2026-03-19T15:00:00",
        "expires_at": "2027-03-19T15:00:00",
    }

    deserialized = domain_rotation_cli._deserialize_domain_record(record)

    assert isinstance(deserialized["purchased_at"], datetime)
    assert deserialized["purchased_at"].year == 2026
    assert isinstance(deserialized["expires_at"], datetime)
    assert deserialized["expires_at"].year == 2027


def test_deserialize_domain_record_parses_legacy_timestamps():
    record = {
        "domain": "example.xyz",
        "price": 2.99,
        "purchased_at": "2026-03-19 15:00:00",
        "expires_at": "2027-03-19",
    }

    deserialized = domain_rotation_cli._deserialize_domain_record(record)

    assert isinstance(deserialized["purchased_at"], datetime)
    assert isinstance(deserialized["expires_at"], datetime)
    assert deserialized["expires_at"].hour == 0


def test_save_manager_state_serializes_domains():
    manager = SimpleNamespace(
        current_spending=2.99,
        active_domain="example.xyz",
        owned_domains=[
            {
                "domain": "example.xyz",
                "price": 2.99,
                "purchased_at": datetime(2026, 3, 19, 15, 0, 0),
                "expires_at": datetime(2027, 3, 19, 15, 0, 0),
            }
        ],
    )

    config = {}
    with patch("domain_rotation_cli.save_config") as mock_save:
        domain_rotation_cli.save_manager_state(manager, config)

    assert config["current_spending"] == 2.99
    assert config["active_domain"] == "example.xyz"
    assert config["owned_domains"][0]["purchased_at"] == "2026-03-19T15:00:00"
    assert config["owned_domains"][0]["expires_at"] == "2027-03-19T15:00:00"
    mock_save.assert_called_once_with(config)


def test_list_domains_handles_legacy_string_timestamps(capsys):
    manager = Mock()
    manager.active_domain = "example.xyz"
    manager.get_owned_domains.return_value = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": "2026-03-19 15:00:00",
            "expires_at": "2027-03-19",
        }
    ]

    with patch("domain_rotation_cli.get_manager", return_value=(manager, {})):
        domain_rotation_cli.list_domains()

    output = capsys.readouterr().out
    assert "example.xyz [ACTIVE]" in output
    assert "Purchased: 2026-03-19 15:00" in output
    assert "Expires: 2027-03-19 00:00" in output
