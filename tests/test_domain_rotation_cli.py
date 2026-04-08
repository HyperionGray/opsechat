"""
Tests for domain rotation CLI state persistence helpers.
"""
from datetime import datetime, timedelta

from domain_manager import DomainRotationManager
from domain_rotation_cli import _format_datetime_for_display, save_manager_state


def test_format_datetime_for_display_handles_datetime_and_strings():
    dt = datetime(2026, 3, 1, 14, 23, 0)
    iso = dt.isoformat()

    assert _format_datetime_for_display(dt, "%Y-%m-%d %H:%M") == "2026-03-01 14:23"
    assert _format_datetime_for_display(iso, "%Y-%m-%d %H:%M") == "2026-03-01 14:23"
    assert _format_datetime_for_display("not-a-date", "%Y-%m-%d") == "not-a-date"


def test_save_manager_state_serializes_datetimes_to_strings():
    manager = DomainRotationManager(monthly_budget=25.0)
    now = datetime(2026, 3, 1, 14, 23, 0)
    manager.current_spending = 2.99
    manager.active_domain = "abc123.xyz"
    manager.owned_domains = [
        {
            "domain": "abc123.xyz",
            "price": 2.99,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365),
        }
    ]

    cfg = {}
    save_manager_state(manager, cfg)

    assert cfg["current_spending"] == 2.99
    assert cfg["active_domain"] == "abc123.xyz"
    assert isinstance(cfg["owned_domains"][0]["purchased_at"], str)
    assert isinstance(cfg["owned_domains"][0]["expires_at"], str)
