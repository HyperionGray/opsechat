"""
Tests for domain_rotation_cli state persistence and migration behavior.
"""
from datetime import datetime, timezone
import json

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


def _write_config(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle)


def _read_config(path):
    with open(path) as handle:
        return json.load(handle)


def test_save_manager_state_serializes_datetime_fields(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager()
    manager.current_spending = 3.5
    manager.active_domain = "alpha.xyz"
    manager.owned_domains = [
        {
            "domain": "alpha.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2027, 3, 1, 12, 0, tzinfo=timezone.utc),
        }
    ]

    config = {"api_key": "pk", "api_secret": "sk", "monthly_budget": 50.0}
    cli.save_manager_state(manager, config)

    persisted = _read_config(config_path)
    domain = persisted["owned_domains"][0]
    assert isinstance(domain["purchased_at"], str)
    assert isinstance(domain["expires_at"], str)
    assert domain["purchased_at"].startswith("2026-03-01T12:00:00")
    assert domain["expires_at"].startswith("2027-03-01T12:00:00")


def test_get_manager_rolls_over_monthly_spending_and_migrates_dates(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "_current_spending_month", lambda: "2026-04")

    _write_config(
        config_path,
        {
            "api_key": "pk",
            "api_secret": "sk",
            "monthly_budget": 25.0,
            "current_spending": 9.0,
            "current_spending_month": "2026-03",
            "active_domain": "legacy.xyz",
            "owned_domains": [
                {
                    "domain": "legacy.xyz",
                    "price": 2.5,
                    "purchased_at": "2026-03-01T10:00:00+00:00",
                }
            ],
        },
    )

    manager, config = cli.get_manager()

    assert manager.current_spending == 0.0
    assert config["current_spending"] == 0.0
    assert config["current_spending_month"] == "2026-04"
    assert manager.active_domain == "legacy.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_list_domains_handles_unparseable_dates(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(cli, "_current_spending_month", lambda: "2026-04")

    _write_config(
        config_path,
        {
            "api_key": "pk",
            "api_secret": "sk",
            "monthly_budget": 10.0,
            "current_spending": 1.0,
            "current_spending_month": "2026-04",
            "active_domain": "bad-date.xyz",
            "owned_domains": [
                {
                    "domain": "bad-date.xyz",
                    "price": 1.0,
                    "purchased_at": "not-a-date",
                    "expires_at": "also-not-a-date",
                }
            ],
        },
    )

    cli.list_domains()
    output = capsys.readouterr().out

    assert "bad-date.xyz [ACTIVE]" in output
    assert "Purchased: Unknown" in output
    assert "Expires: Unknown" in output
