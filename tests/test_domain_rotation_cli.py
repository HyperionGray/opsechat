"""
Tests for domain_rotation_cli persistence and command helpers.
"""

from datetime import datetime
from unittest.mock import Mock

import domain_rotation_cli as cli


def test_owned_domain_datetime_round_trip():
    """Owned-domain timestamps should survive save/load conversion."""
    purchased_at = datetime(2026, 3, 1, 14, 23, 0)
    expires_at = datetime(2027, 3, 1, 14, 23, 0)
    domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }
    ]

    serialized = cli._serialize_owned_domains(domains)
    assert serialized[0]["purchased_at"] == purchased_at.isoformat()
    assert serialized[0]["expires_at"] == expires_at.isoformat()

    deserialized = cli._deserialize_owned_domains(serialized)
    assert deserialized[0]["purchased_at"] == purchased_at
    assert deserialized[0]["expires_at"] == expires_at


def test_save_manager_state_serializes_datetimes(monkeypatch):
    """save_manager_state should persist JSON-safe timestamp values."""
    manager = Mock()
    manager.current_spending = 2.99
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 3, 1, 10, 15, 0),
            "expires_at": datetime(2027, 3, 1, 10, 15, 0),
        }
    ]
    config = {}
    captured = {}

    def fake_save_config(updated):
        captured.update(updated)

    monkeypatch.setattr(cli, "save_config", fake_save_config)
    cli.save_manager_state(manager, config)

    assert isinstance(captured["owned_domains"][0]["purchased_at"], str)
    assert isinstance(captured["owned_domains"][0]["expires_at"], str)
    assert captured["active_domain"] == "active.xyz"
    assert captured["current_spending"] == 2.99


def test_get_manager_deserializes_saved_state(monkeypatch):
    """get_manager should convert persisted timestamp strings to datetime."""
    saved = {
        "api_key": "k",
        "api_secret": "s",
        "monthly_budget": 50.0,
        "current_spending": 3.25,
        "active_domain": "active.xyz",
        "owned_domains": [
            {
                "domain": "active.xyz",
                "price": 3.25,
                "purchased_at": "2026-03-01T10:15:00",
                "expires_at": "2027-03-01T10:15:00",
            }
        ],
    }

    monkeypatch.setattr(cli, "load_config", lambda: saved)
    monkeypatch.setattr(cli, "PorkbunAPIClient", lambda *_: object())

    manager, config = cli.get_manager()

    assert config["active_domain"] == "active.xyz"
    assert manager.current_spending == 3.25
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_set_active_domain_updates_and_saves(monkeypatch):
    """set_active_domain should update active domain when owned."""
    manager = Mock()
    manager.active_domain = "old.xyz"
    manager.get_owned_domains.return_value = [
        {"domain": "old.xyz"},
        {"domain": "new.xyz"},
    ]
    config = {}

    saved = {"called": False}

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, config))

    def fake_save_manager_state(updated_manager, updated_config):
        saved["called"] = True
        assert updated_manager is manager
        assert updated_config is config

    monkeypatch.setattr(cli, "save_manager_state", fake_save_manager_state)
    cli.set_active_domain("new.xyz")

    assert manager.active_domain == "new.xyz"
    assert saved["called"] is True

