"""
Tests for domain_rotation_cli persistence and formatting behavior.
"""
from datetime import datetime

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_get_manager_imports_legacy_state(monkeypatch):
    """Legacy and string-based state should be normalized on load."""
    config = {
        "api_key": "pk_test",
        "api_secret": "sk_test",
        "monthly_budget": "75.5",
        "current_spending": "$5.25",
        "active_domain": "active.example",
        "owned_domains": [
            {
                "domain": "one.example",
                "price": "2.99",
                "purchased_at": "2026-03-01T10:00:00",
                "expires_at": "2027-03-01T10:00:00",
            },
            "legacy.example",
        ],
    }
    monkeypatch.setattr(domain_rotation_cli, "load_config", lambda: config)
    monkeypatch.setattr(domain_rotation_cli, "PorkbunAPIClient", lambda *_: object())

    manager, loaded_config = domain_rotation_cli.get_manager()

    assert loaded_config is config
    assert manager.monthly_budget == 75.5
    assert manager.current_spending == 5.25
    assert manager.active_domain == "active.example"
    assert len(manager.owned_domains) == 2
    assert manager.owned_domains[0]["domain"] == "one.example"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert manager.owned_domains[1]["domain"] == "legacy.example"


def test_save_manager_state_uses_json_safe_export(monkeypatch):
    """Saved manager state should be JSON-serializable and versioned."""
    manager = DomainRotationManager(monthly_budget=55.0)
    manager.import_state(
        {
            "current_spending": 4.25,
            "active_domain": "saved.example",
            "owned_domains": [
                {
                    "domain": "saved.example",
                    "price": 4.25,
                    "purchased_at": datetime(2026, 3, 2, 11, 30).isoformat(),
                    "expires_at": datetime(2027, 3, 2, 11, 30).isoformat(),
                }
            ],
        }
    )
    config = {"api_key": "pk_test", "api_secret": "sk_test"}
    captured = {}
    monkeypatch.setattr(domain_rotation_cli, "save_config", lambda c: captured.update(c))

    domain_rotation_cli.save_manager_state(manager, config)

    assert captured["api_key"] == "pk_test"
    assert captured["state_version"] == 1
    assert captured["active_domain"] == "saved.example"
    assert isinstance(captured["owned_domains"][0]["purchased_at"], str)
    assert captured["owned_domains"][0]["domain"] == "saved.example"


def test_list_domains_formats_string_dates_and_price(monkeypatch, capsys):
    """list output should remain stable even with string date values."""
    manager = DomainRotationManager()
    manager.active_domain = "room.example"
    manager.owned_domains = [
        {
            "domain": "room.example",
            "price": "2.9",
            "purchased_at": "2026-03-01T10:00:00",
            "expires_at": "2027-03-01T10:00:00",
        }
    ]
    monkeypatch.setattr(domain_rotation_cli, "get_manager", lambda: (manager, {}))

    domain_rotation_cli.list_domains()
    output = capsys.readouterr().out

    assert "room.example [ACTIVE]" in output
    assert "Price: $2.90" in output
    assert "Purchased: 2026-03-01 10:00" in output
    assert "Expires: 2027-03-01" in output
