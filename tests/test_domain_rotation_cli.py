"""
Tests for domain_rotation_cli persistence and state management.
"""

import json
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


class _DummyPorkbunClient:
    """Minimal API client stub for CLI manager initialization."""

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret


def _configure_temp_cli_state(monkeypatch, tmp_path, config):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cli, "PorkbunAPIClient", _DummyPorkbunClient)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config))
    return config_file


def test_save_manager_state_serializes_datetimes(monkeypatch, tmp_path):
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=50.0)
    now = datetime(2026, 3, 1, 12, 0, 0)
    manager.current_spending = 2.99
    manager.active_domain = "alpha.xyz"
    manager.owned_domains = [
        {
            "domain": "alpha.xyz",
            "price": 2.99,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    cli.save_manager_state(
        manager,
        {"api_key": "key", "api_secret": "secret", "monthly_budget": 50.0},
    )

    saved = json.loads(config_file.read_text())
    assert saved["active_domain"] == "alpha.xyz"
    assert saved["owned_domains"][0]["purchased_at"] == "2026-03-01T12:00:00"
    assert saved["owned_domains"][0]["expires_at"].startswith("2027-")


def test_get_manager_deserializes_owned_domain_timestamps(monkeypatch, tmp_path):
    config_file = _configure_temp_cli_state(
        monkeypatch,
        tmp_path,
        {
            "api_key": "key",
            "api_secret": "secret",
            "monthly_budget": 60.0,
            "current_spending": 3.5,
            "active_domain": "active.xyz",
            "owned_domains": [
                {
                    "domain": "active.xyz",
                    "price": 3.5,
                    "purchased_at": "2026-03-02T10:15:00",
                    "expires_at": "2027-03-02T10:15:00",
                }
            ],
        },
    )

    manager, _ = cli.get_manager()

    assert config_file.exists()
    assert manager.active_domain == "active.xyz"
    assert manager.current_spending == 3.5
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_get_manager_skips_malformed_owned_domain_entries(monkeypatch, tmp_path):
    _configure_temp_cli_state(
        monkeypatch,
        tmp_path,
        {
            "api_key": "key",
            "api_secret": "secret",
            "owned_domains": [
                {"price": 1.23},  # missing domain
                "invalid-entry",
                {"domain": "kept.xyz", "purchased_at": "not-a-date", "expires_at": ""},
            ],
        },
    )

    manager, _ = cli.get_manager()

    assert len(manager.owned_domains) == 1
    assert manager.owned_domains[0]["domain"] == "kept.xyz"
    assert manager.owned_domains[0]["purchased_at"] is None


def test_prune_state_removes_expired_and_repairs_active_domain(monkeypatch, tmp_path):
    now = datetime.now()
    _configure_temp_cli_state(
        monkeypatch,
        tmp_path,
        {
            "api_key": "key",
            "api_secret": "secret",
            "active_domain": "expired.xyz",
            "owned_domains": [
                {
                    "domain": "expired.xyz",
                    "price": 1.0,
                    "purchased_at": (now - timedelta(days=10)).isoformat(),
                    "expires_at": (now - timedelta(days=1)).isoformat(),
                },
                {
                    "domain": "fresh.xyz",
                    "price": 2.0,
                    "purchased_at": now.isoformat(),
                    "expires_at": (now + timedelta(days=30)).isoformat(),
                },
            ],
        },
    )

    cli.prune_state()
    saved = cli.load_config()

    assert saved["active_domain"] == "fresh.xyz"
    assert len(saved["owned_domains"]) == 1
    assert saved["owned_domains"][0]["domain"] == "fresh.xyz"
