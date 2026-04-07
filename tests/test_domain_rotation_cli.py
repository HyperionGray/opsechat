"""
Tests for domain_rotation_cli state handling helpers.
"""

import json
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetime_fields(tmp_path, monkeypatch):
    """Manager state is persisted as JSON-safe datetime strings."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=25.0)
    now = datetime.now().replace(microsecond=0)
    manager.current_spending = 3.14
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 1.99,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    cli.save_manager_state(manager, {}, quiet=True)

    persisted = json.loads(config_file.read_text())
    domain = persisted["owned_domains"][0]
    assert isinstance(domain["purchased_at"], str)
    assert isinstance(domain["expires_at"], str)
    assert persisted["active_domain"] == "active.xyz"
    assert persisted["current_spending"] == 3.14


def test_get_manager_prunes_expired_domains_from_loaded_config(tmp_path, monkeypatch):
    """Loading manager state auto-prunes expired domains and persists cleanup."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cli, "PorkbunAPIClient", lambda _key, _secret: object())

    now = datetime.now().replace(microsecond=0)
    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 50,
        "current_spending": "2.99",
        "active_domain": "old.xyz",
        "owned_domains": [
            {
                "domain": "old.xyz",
                "price": 1.0,
                "purchased_at": (now - timedelta(days=366)).isoformat(),
                "expires_at": (now - timedelta(days=1)).isoformat(),
            },
            {
                "domain": "new.xyz",
                "price": 2.0,
                "purchased_at": now.isoformat(),
                "expires_at": (now + timedelta(days=30)).isoformat(),
            },
        ],
    }
    config_file.write_text(json.dumps(config))

    manager, _ = cli.get_manager()

    assert [d["domain"] for d in manager.owned_domains] == ["new.xyz"]
    assert manager.active_domain == "new.xyz"
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)

    persisted = json.loads(config_file.read_text())
    assert [d["domain"] for d in persisted["owned_domains"]] == ["new.xyz"]
    assert persisted["active_domain"] == "new.xyz"


def test_list_domains_handles_string_datetime_values(monkeypatch, capsys):
    """List command formats datetime-like strings safely."""
    now = datetime.now().replace(microsecond=0)
    manager = DomainRotationManager()
    manager.active_domain = "shown.xyz"
    manager.owned_domains = [
        {
            "domain": "shown.xyz",
            "price": 1.25,
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
        }
    ]

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {}))

    cli.list_domains()
    output = capsys.readouterr().out
    assert "shown.xyz [ACTIVE]" in output
    assert "Purchased:" in output
    assert "Expires:" in output
