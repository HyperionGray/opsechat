"""
Tests for domain rotation CLI state persistence.
"""
from datetime import datetime
from types import SimpleNamespace

import domain_rotation_cli as cli


def test_save_manager_state_serializes_datetime(monkeypatch):
    """Owned-domain datetime fields should be JSON-safe strings."""
    manager = SimpleNamespace(
        current_spending=2.75,
        active_domain="alpha123.xyz",
        owned_domains=[
            {
                "domain": "alpha123.xyz",
                "price": 2.75,
                "purchased_at": datetime(2026, 3, 1, 12, 30, 0),
                "expires_at": datetime(2027, 3, 1, 12, 30, 0),
            }
        ],
    )
    config = {}
    monkeypatch.setattr(cli, "save_config", lambda *_args, **_kwargs: None)

    cli.save_manager_state(manager, config)

    saved = config["owned_domains"][0]
    assert saved["purchased_at"] == "2026-03-01T12:30:00"
    assert saved["expires_at"] == "2027-03-01T12:30:00"


def test_get_manager_restores_datetime_from_config(monkeypatch):
    """Persisted ISO strings should restore to datetime values."""
    config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": 30.0,
        "current_spending": 4.2,
        "active_domain": "beta789.xyz",
        "owned_domains": [
            {
                "domain": "beta789.xyz",
                "price": 4.2,
                "purchased_at": "2026-03-10T09:00:00",
                "expires_at": "2027-03-10T09:00:00",
            }
        ],
    }
    monkeypatch.setattr(cli, "load_config", lambda: config)

    manager, _loaded_config = cli.get_manager()

    assert manager.current_spending == 4.2
    assert manager.active_domain == "beta789.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_list_domains_handles_string_timestamps(monkeypatch, capsys):
    """Listing should tolerate legacy string timestamps without crashing."""
    manager = SimpleNamespace(
        active_domain="gamma777.xyz",
        get_owned_domains=lambda: [
            {
                "domain": "gamma777.xyz",
                "price": 1.99,
                "purchased_at": "2026-03-11T14:45:00",
                "expires_at": "2027-03-11T14:45:00",
            }
        ],
    )
    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {}))

    cli.list_domains()
    output = capsys.readouterr().out

    assert "gamma777.xyz [ACTIVE]" in output
    assert "Purchased: 2026-03-11 14:45" in output
    assert "Expires: 2027-03-11" in output
