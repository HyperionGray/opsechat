"""
Tests for domain rotation CLI registrar selection and state serialization.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

import domain_rotation_cli
from domain_manager import NamecheapAPIClient, PorkbunAPIClient


def test_get_manager_uses_porkbun_when_configured():
    """CLI builds a Porkbun client when registrar is porkbun."""
    config = {
        "registrar": "porkbun",
        "api_key": "pk_live",
        "api_secret": "sk_live",
        "monthly_budget": 20.0,
    }
    with patch.object(domain_rotation_cli, "load_config", return_value=config):
        manager, loaded = domain_rotation_cli.get_manager()
    assert isinstance(manager.api_client, PorkbunAPIClient)
    assert manager.registrar == "porkbun"
    assert loaded["registrar"] == "porkbun"


def test_get_manager_uses_namecheap_when_configured():
    """CLI builds a Namecheap client when registrar is namecheap."""
    config = {
        "registrar": "namecheap",
        "api_key": "nc_key",
        "namecheap_username": "nc_user",
        "namecheap_client_ip": "127.0.0.1",
        "namecheap_use_sandbox": True,
        "namecheap_default_contact": {
            "FirstName": "Test",
            "LastName": "User",
            "Address1": "1 Main St",
            "City": "Austin",
            "StateProvince": "TX",
            "PostalCode": "78701",
            "Country": "US",
            "Phone": "+1.5555555555",
            "EmailAddress": "test@example.com",
        },
        "monthly_budget": 30.0,
    }
    with patch.object(domain_rotation_cli, "load_config", return_value=config):
        manager, _ = domain_rotation_cli.get_manager()
    assert isinstance(manager.api_client, NamecheapAPIClient)
    assert manager.registrar == "namecheap"


def test_get_manager_requires_namecheap_username():
    """CLI exits for incomplete Namecheap config."""
    config = {"registrar": "namecheap", "api_key": "nc_key"}
    with patch.object(domain_rotation_cli, "load_config", return_value=config):
        with pytest.raises(SystemExit):
            domain_rotation_cli.get_manager()


def test_save_manager_state_serializes_datetimes():
    """CLI persists owned domain datetimes as ISO strings."""
    manager = domain_rotation_cli.DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.99
    manager.active_domain = "abc.xyz"
    manager.owned_domains = [
        {
            "domain": "abc.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 4, 8, 9, 0, 0),
            "expires_at": datetime(2027, 4, 8, 9, 0, 0),
        }
    ]
    config = {}
    with patch.object(domain_rotation_cli, "save_config") as mock_save:
        domain_rotation_cli.save_manager_state(manager, config)
    assert isinstance(config["owned_domains"][0]["purchased_at"], str)
    assert config["active_domain"] == "abc.xyz"
    assert config["current_spending"] == 2.99
    mock_save.assert_called_once()
