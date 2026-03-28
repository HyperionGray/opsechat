"""
Tests for domain_rotation_cli persistence helpers and state loading.
"""

import json
from datetime import datetime

import domain_rotation_cli as cli


def test_serialize_owned_domains_converts_datetimes():
    domains = [
        {
            "domain": "alpha.xyz",
            "price": 1.99,
            "purchased_at": datetime(2026, 3, 28, 10, 30, 0),
            "expires_at": datetime(2027, 3, 28, 10, 30, 0),
        }
    ]

    serialized = cli._serialize_owned_domains(domains)

    assert serialized[0]["purchased_at"] == "2026-03-28T10:30:00"
    assert serialized[0]["expires_at"] == "2027-03-28T10:30:00"


def test_deserialize_owned_domains_supports_iso_and_z():
    hydrated = cli._deserialize_owned_domains(
        [
            {
                "domain": "beta.xyz",
                "price": 0.99,
                "purchased_at": "2026-03-28T10:30:00Z",
                "expires_at": "2027-03-28T10:30:00+00:00",
            }
        ]
    )

    assert isinstance(hydrated[0]["purchased_at"], datetime)
    assert isinstance(hydrated[0]["expires_at"], datetime)
    assert hydrated[0]["purchased_at"].year == 2026
    assert hydrated[0]["expires_at"].year == 2027


def test_get_manager_loads_legacy_persisted_state(monkeypatch, tmp_path):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    legacy_config = {
        "api_key": "test-key",
        "api_secret": "test-secret",
        "monthly_budget": "50.5",
        "current_spending": "2.75",
        "owned_domains": [
            {
                "domain": "gamma.xyz",
                "price": 2.75,
                "purchased_at": "2026-03-28T10:15:00Z",
                "expires_at": "2027-03-28 10:15:00",
            }
        ],
        "active_domain": "gamma.xyz",
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(legacy_config), encoding="utf-8")

    manager, loaded_config = cli.get_manager()

    assert manager.monthly_budget == 50.5
    assert manager.current_spending == 2.75
    assert manager.active_domain == "gamma.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)

    cli.save_manager_state(manager, loaded_config)
    persisted = json.loads(config_path.read_text(encoding="utf-8"))

    assert isinstance(persisted["owned_domains"][0]["purchased_at"], str)
    assert isinstance(persisted["owned_domains"][0]["expires_at"], str)
