"""
Tests for domain_rotation_cli.py helpers and configuration handling.
"""
from datetime import datetime

import domain_rotation_cli as cli


def test_serialize_deserialize_owned_domains_roundtrip():
    """Datetime values should roundtrip through JSON-safe serialization."""
    now = datetime.now()
    domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "registrar": "porkbun",
            "purchased_at": now,
            "expires_at": now,
        }
    ]
    serialized = cli._serialize_owned_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    restored = cli._deserialize_owned_domains(serialized)
    assert isinstance(restored[0]["purchased_at"], datetime)
    assert isinstance(restored[0]["expires_at"], datetime)


def test_get_namecheap_contact_from_config_maps_fields():
    """Namecheap contact field mapping should produce API-ready keys."""
    config = {
        "namecheap_contact_firstname": "Alice",
        "namecheap_contact_lastname": "Operator",
        "namecheap_contact_address1": "1 Main St",
        "namecheap_contact_city": "Austin",
        "namecheap_contact_stateprovince": "TX",
        "namecheap_contact_postalcode": "78701",
        "namecheap_contact_country": "US",
        "namecheap_contact_phone": "+1.5555551212",
        "namecheap_contact_emailaddress": "alice@example.com",
    }
    contact = cli._get_namecheap_contact_from_config(config)
    assert contact["FirstName"] == "Alice"
    assert contact["LastName"] == "Operator"
    assert contact["EmailAddress"] == "alice@example.com"


def test_get_manager_uses_namecheap_client(monkeypatch):
    """get_manager should initialize Namecheap path when registrar is configured."""
    fake_config = {
        "registrar": "namecheap",
        "api_key": "key-1",
        "api_username": "api-user",
        "client_ip": "127.0.0.1",
        "sandbox": True,
        "monthly_budget": 12.5,
        "current_spending": 1.0,
        "owned_domains": [],
        "active_domain": None,
    }
    monkeypatch.setattr(cli, "load_config", lambda: fake_config)

    manager, config = cli.get_manager()
    assert config["registrar"] == "namecheap"
    assert manager.active_registrar == "namecheap"
    assert manager.monthly_budget == 12.5

