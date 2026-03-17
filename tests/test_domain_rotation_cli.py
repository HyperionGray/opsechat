"""
Tests for domain rotation CLI state handling and cleanup.
"""

from datetime import datetime, timedelta

from domain_manager import DomainRotationManager
import domain_rotation_cli as cli


def test_save_and_load_manager_state_round_trip(monkeypatch, tmp_path):
    """Datetime values should persist and rehydrate correctly."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    config = {
        "api_key": "key",
        "api_secret": "secret",
        "monthly_budget": 50.0,
    }
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.99
    manager.active_domain = "alpha123.xyz"
    manager.owned_domains = [{
        "domain": "alpha123.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 3, 1, 12, 0, 0),
        "expires_at": datetime(2027, 3, 1, 12, 0, 0),
    }]

    cli.save_manager_state(manager, config)

    raw_config = cli.load_config()
    assert isinstance(raw_config["owned_domains"][0]["purchased_at"], str)
    assert raw_config["state_version"] == cli.STATE_VERSION

    loaded_manager, _ = cli.get_manager()
    assert loaded_manager.active_domain == "alpha123.xyz"
    assert isinstance(loaded_manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(loaded_manager.owned_domains[0]["expires_at"], datetime)


def test_cleanup_expired_domains_repairs_active_domain():
    """Cleanup should drop expired entries and keep active domain valid."""
    now = datetime.now()
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.owned_domains = [
        {
            "domain": "expired001.xyz",
            "price": 1.0,
            "purchased_at": now - timedelta(days=700),
            "expires_at": now - timedelta(days=1),
        },
        {
            "domain": "live001.xyz",
            "price": 2.0,
            "purchased_at": now - timedelta(days=10),
            "expires_at": now + timedelta(days=355),
        },
    ]
    manager.active_domain = "expired001.xyz"

    removed = cli.cleanup_expired_domains(manager)

    assert removed == 1
    assert len(manager.owned_domains) == 1
    assert manager.owned_domains[0]["domain"] == "live001.xyz"
    assert manager.active_domain == "live001.xyz"


def test_normalize_owned_domains_handles_legacy_values():
    """Legacy config values (strings and missing fields) should normalize."""
    normalized = cli._normalize_owned_domains([  # pylint: disable=protected-access
        {
            "domain": "legacy001.xyz",
            "price": "1.99",
            "purchased_at": "2026-03-01T10:00:00",
            "expires_at": "2027-03-01T10:00:00",
        },
        {
            "domain": "legacy002.xyz",
            "price": "not-a-number",
        },
        "invalid-record",
    ])

    assert len(normalized) == 2
    assert normalized[0]["price"] == 1.99
    assert isinstance(normalized[0]["purchased_at"], datetime)
    assert normalized[1]["price"] == 0.0
