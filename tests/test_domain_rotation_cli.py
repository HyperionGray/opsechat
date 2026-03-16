"""
Tests for domain rotation CLI helpers.
"""
from datetime import datetime

from domain_rotation_cli import (
    _serialize_owned_domains,
    _deserialize_owned_domains,
    _build_client_from_config,
)
from domain_manager import PorkbunAPIClient, NamecheapAPIClient


def test_owned_domain_datetime_roundtrip():
    purchased_at = datetime(2026, 3, 16, 10, 30, 0)
    expires_at = datetime(2027, 3, 16, 10, 30, 0)
    domains = [{
        "domain": "example.xyz",
        "provider": "porkbun",
        "price": 2.99,
        "purchased_at": purchased_at,
        "expires_at": expires_at,
    }]

    serialized = _serialize_owned_domains(domains)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    deserialized = _deserialize_owned_domains(serialized)
    assert deserialized[0]["purchased_at"] == purchased_at
    assert deserialized[0]["expires_at"] == expires_at


def test_build_client_from_config_porkbun():
    client, provider = _build_client_from_config({
        "registrar": "porkbun",
        "api_key": "pk",
        "api_secret": "sk",
    })
    assert provider == "porkbun"
    assert isinstance(client, PorkbunAPIClient)


def test_build_client_from_config_namecheap():
    client, provider = _build_client_from_config({
        "registrar": "namecheap",
        "namecheap_api_key": "nk",
        "namecheap_username": "user",
        "namecheap_client_ip": "127.0.0.1",
    })
    assert provider == "namecheap"
    assert isinstance(client, NamecheapAPIClient)
