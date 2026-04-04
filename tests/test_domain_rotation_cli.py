"""
Tests for domain rotation CLI helpers and persistence behavior.
"""
from datetime import datetime

from domain_manager import DomainRotationManager
from domain_rotation_cli import (
    _deserialize_owned_domains,
    _normalize_provider_strategy,
    _serialize_owned_domains,
)


def test_provider_strategy_normalization():
    """CLI should normalize configured provider strategy."""
    assert _normalize_provider_strategy(" PRIORITY ") == "priority"
    assert _normalize_provider_strategy("cheapest") == "cheapest"


def test_provider_strategy_normalization_invalid():
    """CLI should reject unsupported provider strategies."""
    try:
        _normalize_provider_strategy("round-robin")
        assert False, "Expected ValueError for unsupported strategy"
    except ValueError:
        assert True


def test_owned_domains_datetime_round_trip():
    """Owned domains should round-trip through JSON-safe representation."""
    purchased_at = datetime(2026, 4, 1, 12, 30, 0)
    expires_at = datetime(2027, 4, 1, 12, 30, 0)
    raw = [{
        "domain": "example.xyz",
        "price": 1.99,
        "provider": "primary",
        "purchased_at": purchased_at,
        "expires_at": expires_at,
    }]

    serialized = _serialize_owned_domains(raw)
    assert isinstance(serialized[0]["purchased_at"], str)
    assert isinstance(serialized[0]["expires_at"], str)

    restored = _deserialize_owned_domains(serialized)
    assert restored[0]["purchased_at"] == purchased_at
    assert restored[0]["expires_at"] == expires_at


def test_owned_domains_deserialization_preserves_unparseable_dates():
    """Invalid persisted date strings should not crash deserialization."""
    raw = [{
        "domain": "example.xyz",
        "price": 2.49,
        "purchased_at": "not-a-date",
        "expires_at": "also-not-a-date",
    }]

    restored = _deserialize_owned_domains(raw)
    assert restored[0]["purchased_at"] == "not-a-date"
    assert restored[0]["expires_at"] == "also-not-a-date"


def test_purchase_uses_provider_from_search_result():
    """CLI flow relies on provider-aware purchase behavior."""
    manager = DomainRotationManager(monthly_budget=50.0, provider_strategy="cheapest")

    class _Client:
        def __init__(self, price):
            self.price = price
            self.purchases = 0

        def search_domain(self, domain):
            return {"available": True, "price": self.price}

        def purchase_domain(self, domain, years=1):
            self.purchases += 1
            return {"success": True, "domain": domain}

        def get_pricing(self, tld):
            return {}

    expensive = _Client("3.99")
    cheap = _Client("1.05")
    manager.add_api_client("expensive", expensive, make_primary=True)
    manager.add_api_client("cheap", cheap)

    result = manager.rotate_domain()
    assert result is not None
    assert expensive.purchases == 0
    assert cheap.purchases == 1
