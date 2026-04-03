"""
Tests for domain_rotation_cli module helpers and manager wiring.
"""
from datetime import datetime, timedelta

import domain_rotation_cli as cli
from domain_manager import NamecheapAPIClient, PorkbunAPIClient


def test_serialize_deserialize_domains_roundtrip():
    """Datetime fields should survive JSON-safe roundtrip helpers."""
    purchased_at = datetime.now()
    expires_at = purchased_at + timedelta(days=365)
    domains = [{
        "domain": "test123.xyz",
        "price": 2.99,
        "purchased_at": purchased_at,
        "expires_at": expires_at,
    }]

    serialized = cli._serialize_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = cli._deserialize_domains(serialized)
    assert restored[0]["domain"] == "test123.xyz"
    assert restored[0]["price"] == 2.99
    assert isinstance(restored[0]["purchased_at"], datetime)
    assert isinstance(restored[0]["expires_at"], datetime)


def test_get_manager_uses_namecheap_client(monkeypatch):
    """get_manager should wire Namecheap when registrar is configured."""
    config = {
        "registrar": "namecheap",
        "api_user": "nc-user",
        "api_key": "nc-key",
        "username": "nc-username",
        "client_ip": "203.0.113.10",
        "default_contacts": {"FirstName": "A"},
        "monthly_budget": 35.0,
        "current_spending": 5.0,
        "owned_domains": [{
            "domain": "alpha.xyz",
            "price": 2.0,
            "purchased_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=10)).isoformat(),
        }],
        "active_domain": "alpha.xyz",
    }
    monkeypatch.setattr(cli, "load_config", lambda: config)

    manager, loaded_config = cli.get_manager()

    assert isinstance(manager.api_client, NamecheapAPIClient)
    assert manager.monthly_budget == 35.0
    assert manager.current_spending == 5.0
    assert manager.active_domain == "alpha.xyz"
    assert loaded_config["registrar"] == "namecheap"


def test_get_manager_uses_porkbun_client(monkeypatch):
    """get_manager should wire Porkbun by default."""
    config = {
        "registrar": "porkbun",
        "api_key": "pb-key",
        "api_secret": "pb-secret",
        "monthly_budget": 15.0,
    }
    monkeypatch.setattr(cli, "load_config", lambda: config)

    manager, _ = cli.get_manager()

    assert isinstance(manager.api_client, PorkbunAPIClient)
    assert manager.monthly_budget == 15.0
