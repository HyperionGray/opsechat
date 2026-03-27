"""
Tests for domain_rotation_cli state handling.
"""
from datetime import datetime

import domain_rotation_cli as cli


def test_parse_datetime_for_display_handles_iso_and_invalid():
    dt = cli._parse_datetime_for_display("2026-03-10T10:11:12")
    assert isinstance(dt, datetime)
    assert dt.year == 2026

    assert cli._parse_datetime_for_display("not-a-date") is None
    assert cli._parse_datetime_for_display(None) is None


def test_save_manager_state_uses_export_state(monkeypatch):
    class DummyManager:
        def export_state(self):
            return {
                "current_spending": 3.5,
                "owned_domains": [{"domain": "x.xyz"}],
                "active_domain": "x.xyz",
                "last_budget_reset_period": "2026-03",
            }

    config = {"api_key": "k", "api_secret": "s", "monthly_budget": 50.0}
    captured = {}

    def fake_save_config(updated):
        captured["config"] = updated.copy()

    monkeypatch.setattr(cli, "save_config", fake_save_config)

    cli.save_manager_state(DummyManager(), config, quiet=False)

    assert captured["config"]["current_spending"] == 3.5
    assert captured["config"]["active_domain"] == "x.xyz"
    assert captured["config"]["last_budget_reset_period"] == "2026-03"
    assert captured["config"]["owned_domains"][0]["domain"] == "x.xyz"

