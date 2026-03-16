"""
Tests for domain_rotation_cli state persistence helpers.
"""

from datetime import datetime, timedelta

from domain_manager import DomainRotationManager
import domain_rotation_cli as cli


def test_serialize_deserialize_domain_entry_round_trip():
    entry = {
        "domain": "alpha.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 1, 1, 12, 0, 0),
        "expires_at": datetime(2027, 1, 1, 12, 0, 0),
    }

    serialized = cli._serialize_domain_entry(entry)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    deserialized = cli._deserialize_domain_entry(serialized)
    assert deserialized["purchased_at"] == entry["purchased_at"]
    assert deserialized["expires_at"] == entry["expires_at"]


def test_save_manager_state_serializes_datetime_values(monkeypatch):
    manager = DomainRotationManager(monthly_budget=20.0)
    manager.current_spending = 4.5
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 2.25,
            "purchased_at": datetime(2026, 2, 1, 9, 30, 0),
            "expires_at": datetime(2027, 2, 1, 9, 30, 0),
        }
    ]
    config = {}
    captured = {}

    def _fake_save_config(updated_config):
        captured.update(updated_config)

    monkeypatch.setattr(cli, "save_config", _fake_save_config)
    cli.save_manager_state(manager, config)

    assert captured["current_spending"] == 4.5
    assert captured["active_domain"] == "active.xyz"
    assert isinstance(captured["owned_domains"][0]["purchased_at"], str)
    assert isinstance(captured["owned_domains"][0]["expires_at"], str)


def test_get_manager_deserializes_saved_domains(monkeypatch):
    class DummyClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    monkeypatch.setattr(cli, "PorkbunAPIClient", DummyClient)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: {
            "api_key": "k",
            "api_secret": "s",
            "monthly_budget": 10.0,
            "current_spending": 2.0,
            "active_domain": "alpha.xyz",
            "owned_domains": [
                {
                    "domain": "alpha.xyz",
                    "price": 2.0,
                    "purchased_at": "2026-01-01T12:00:00",
                    "expires_at": "2027-01-01T12:00:00",
                }
            ],
        },
    )

    manager, _ = cli.get_manager()
    assert manager.current_spending == 2.0
    assert manager.active_domain == "alpha.xyz"
    assert manager.owned_domains[0]["domain"] == "alpha.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_prune_expired_domains_removes_expired_and_updates_active(monkeypatch):
    manager = DomainRotationManager(monthly_budget=50.0)
    now = datetime.now()
    manager.owned_domains = [
        {
            "domain": "expired.xyz",
            "price": 1.0,
            "purchased_at": now - timedelta(days=400),
            "expires_at": now - timedelta(days=1),
        },
        {
            "domain": "fresh.xyz",
            "price": 2.0,
            "purchased_at": now - timedelta(days=10),
            "expires_at": now + timedelta(days=355),
        },
    ]
    manager.active_domain = "expired.xyz"
    config = {}
    saved = {"called": False}

    def _fake_get_manager():
        return manager, config

    def _fake_save_manager_state(updated_manager, updated_config):
        saved["called"] = True
        assert updated_manager is manager
        assert updated_config is config

    monkeypatch.setattr(cli, "get_manager", _fake_get_manager)
    monkeypatch.setattr(cli, "save_manager_state", _fake_save_manager_state)

    cli.prune_expired_domains()

    assert saved["called"] is True
    assert len(manager.owned_domains) == 1
    assert manager.owned_domains[0]["domain"] == "fresh.xyz"
    assert manager.active_domain == "fresh.xyz"
