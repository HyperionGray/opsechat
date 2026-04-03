"""
Tests for domain_rotation_cli persistence and datetime handling.
"""

from datetime import datetime, timezone

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_serialize_owned_domains_converts_datetime_fields_to_iso():
    domains = [
        {
            "domain": "alpha.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 4, 1, 12, 30, tzinfo=timezone.utc),
            "expires_at": datetime(2027, 4, 1, 12, 30, tzinfo=timezone.utc),
        }
    ]

    serialized = cli._serialize_owned_domains(domains)

    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)
    assert serialized[0]["purchased_at"].endswith("+00:00")


def test_deserialize_owned_domains_parses_iso_and_zulu_datetimes():
    domains = [
        {
            "domain": "beta.xyz",
            "price": 2.50,
            "purchased_at": "2026-04-01T12:30:00+00:00",
            "expires_at": "2027-04-01T12:30:00Z",
        }
    ]

    deserialized = cli._deserialize_owned_domains(domains)

    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)
    assert deserialized[0]["expires_at"].tzinfo is not None


def test_get_manager_deserializes_persisted_state(monkeypatch):
    config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 25.0,
        "current_spending": "7.5",
        "active_domain": "active.xyz",
        "owned_domains": [
            {
                "domain": "active.xyz",
                "price": 1.99,
                "purchased_at": "2026-04-01T12:30:00+00:00",
                "expires_at": "2027-04-01T12:30:00+00:00",
            }
        ],
    }

    fake_client = object()
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "PorkbunAPIClient", lambda *_args, **_kwargs: fake_client)

    manager, returned_config = cli.get_manager()

    assert returned_config is config
    assert manager.api_client is fake_client
    assert manager.current_spending == 7.5
    assert manager.active_domain == "active.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)


def test_get_manager_invalid_current_spending_falls_back_to_zero(monkeypatch):
    config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "current_spending": "not-a-number",
        "owned_domains": [],
    }

    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "PorkbunAPIClient", lambda *_args, **_kwargs: object())

    manager, _ = cli.get_manager()

    assert manager.current_spending == 0.0


def test_save_manager_state_serializes_datetime_values(monkeypatch):
    manager = DomainRotationManager(monthly_budget=10.0)
    manager.current_spending = 3.25
    manager.active_domain = "saved.xyz"
    manager.owned_domains = [
        {
            "domain": "saved.xyz",
            "price": 3.25,
            "purchased_at": datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2027, 4, 1, 12, 0, tzinfo=timezone.utc),
        }
    ]

    captured = {}

    def _capture_save(config):
        captured["config"] = config

    monkeypatch.setattr(cli, "save_config", _capture_save)

    config = {}
    cli.save_manager_state(manager, config)

    assert config["current_spending"] == 3.25
    assert config["active_domain"] == "saved.xyz"
    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert "config" in captured
