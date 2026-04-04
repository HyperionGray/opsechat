"""
Tests for domain_rotation_cli helper behavior.
"""
from datetime import datetime, timedelta

from domain_manager import DomainRotationManager
import domain_rotation_cli


def test_save_manager_state_serializes_datetime_values(monkeypatch):
    saved = {}

    def _fake_save_config(config):
        saved.update(config)

    monkeypatch.setattr(domain_rotation_cli, "save_config", _fake_save_config)

    manager = DomainRotationManager()
    manager.current_spending = 5.25
    manager.active_domain = "active.example"
    manager.owned_domains = [
        {
            "domain": "active.example",
            "price": 1.99,
            "purchased_at": datetime(2026, 4, 1, 10, 0, 0),
            "expires_at": datetime(2027, 4, 1, 10, 0, 0),
        }
    ]

    config = {"api_key": "pk_test", "api_secret": "sk_test", "monthly_budget": 50.0}
    domain_rotation_cli.save_manager_state(manager, config)

    assert config["current_spending"] == 5.25
    assert config["active_domain"] == "active.example"
    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert isinstance(config["owned_domains"][0]["expires_at"], str)
    assert saved["active_domain"] == "active.example"


def test_manager_import_state_normalizes_cli_loaded_config():
    manager = DomainRotationManager()
    config = {
        "current_spending": "3.50",
        "active_domain": "kept.example",
        "owned_domains": [
            {
                "domain": "kept.example",
                "price": "$1.99",
                "purchased_at": "2026-04-01T10:00:00",
                "expires_at": "2027-04-01T10:00:00",
            },
            {
                "domain": "expired.example",
                "price": "2.50",
                "purchased_at": "2024-01-01T00:00:00",
                "expires_at": "2025-01-01T00:00:00",
            },
        ],
    }

    manager.import_state(config)
    assert manager.current_spending == 3.5
    assert manager.active_domain == "kept.example"
    assert len(manager.owned_domains) == 2
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)

    removed = manager.cleanup_expired_domains(now=datetime(2026, 4, 2, 0, 0, 0))
    assert removed == 1
    assert len(manager.owned_domains) == 1
    assert manager.owned_domains[0]["domain"] == "kept.example"

