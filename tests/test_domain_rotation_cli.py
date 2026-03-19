import json
from datetime import datetime, timedelta

import domain_rotation_cli
from domain_manager import DomainRotationManager


def test_save_manager_state_serializes_datetime_fields(monkeypatch, tmp_path):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    manager = DomainRotationManager(monthly_budget=25.0)
    manager.current_spending = 2.5
    manager.active_domain = "alpha.xyz"
    manager.owned_domains = [{
        "domain": "alpha.xyz",
        "price": 2.5,
        "purchased_at": datetime(2026, 1, 1, 10, 30, 0),
        "expires_at": datetime(2027, 1, 1, 10, 30, 0),
    }]
    config = {"api_key": "pk", "api_secret": "sk"}

    domain_rotation_cli.save_manager_state(manager, config)

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["active_domain"] == "alpha.xyz"
    assert isinstance(persisted["owned_domains"][0]["purchased_at"], str)
    assert isinstance(persisted["owned_domains"][0]["expires_at"], str)


def test_get_manager_deserializes_and_prunes_expired_domains(monkeypatch, tmp_path):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    expired = (now - timedelta(days=1)).isoformat()
    valid = (now + timedelta(days=10)).isoformat()

    config_path.write_text(json.dumps({
        "api_key": "pk_test_123",
        "api_secret": "sk_test_456",
        "monthly_budget": 50.0,
        "active_domain": "expired.xyz",
        "owned_domains": [
            {"domain": "expired.xyz", "price": 1.0, "expires_at": expired},
            {"domain": "current.xyz", "price": 2.0, "expires_at": valid},
        ],
    }), encoding="utf-8")

    manager, _ = domain_rotation_cli.get_manager()

    assert manager.active_domain == "current.xyz"
    assert len(manager.owned_domains) == 1
    assert manager.owned_domains[0]["domain"] == "current.xyz"
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_format_timestamp_handles_iso_strings():
    rendered = domain_rotation_cli._format_timestamp("2026-02-20T12:34:56", "%Y-%m-%d")
    assert rendered == "2026-02-20"
