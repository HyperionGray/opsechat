"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime

from domain_manager import DomainRotationManager
import domain_rotation_cli


def test_serialize_and_deserialize_owned_domains_roundtrip():
    """CLI state helpers should roundtrip datetime fields safely."""
    original = [{
        "domain": "roundtrip.xyz",
        "price": 2.99,
        "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
        "expires_at": datetime(2027, 1, 2, 3, 4, 5),
    }]

    serialized = domain_rotation_cli.serialize_owned_domains(original)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = domain_rotation_cli.deserialize_owned_domains(serialized)
    assert isinstance(deserialized[0]["purchased_at"], datetime)
    assert isinstance(deserialized[0]["expires_at"], datetime)


def test_get_manager_namecheap_deserializes_state(monkeypatch):
    """get_manager should construct Namecheap client and parse persisted timestamps."""
    persisted_config = {
        "registrar": "namecheap",
        "api_key": "nc_key",
        "username": "nc_user",
        "client_ip": "127.0.0.1",
        "monthly_budget": 45.0,
        "current_spending": 4.5,
        "active_domain": "active.xyz",
        "owned_domains": [{
            "domain": "active.xyz",
            "price": 3.0,
            "purchased_at": "2026-01-01T01:02:03",
            "expires_at": "2027-01-01T01:02:03",
        }],
    }
    monkeypatch.setattr(domain_rotation_cli, "load_config", lambda: persisted_config)

    manager, config = domain_rotation_cli.get_manager()

    assert manager.registrar == "namecheap"
    assert manager.monthly_budget == 45.0
    assert manager.current_spending == 4.5
    assert manager.active_domain == "active.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert config["registrar"] == "namecheap"


def test_save_manager_state_serializes_datetimes(monkeypatch):
    """save_manager_state should leave config JSON-serializable."""
    manager = DomainRotationManager(monthly_budget=50.0)
    manager.registrar = "porkbun"
    manager.current_spending = 3.0
    manager.active_domain = "saved.xyz"
    manager.owned_domains = [{
        "domain": "saved.xyz",
        "price": 3.0,
        "purchased_at": datetime(2026, 2, 3, 4, 5, 6),
        "expires_at": datetime(2027, 2, 3, 4, 5, 6),
    }]

    captured = {}
    monkeypatch.setattr(domain_rotation_cli, "save_config", lambda cfg: None)
    domain_rotation_cli.save_manager_state(manager, captured)

    assert captured["registrar"] == "porkbun"
    assert isinstance(captured["owned_domains"][0]["purchased_at"], str)
    assert isinstance(captured["owned_domains"][0]["expires_at"], str)
