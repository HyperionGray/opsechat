"""
Tests for domain_rotation_cli state persistence and argument parsing.
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import domain_rotation_cli as cli


def test_domain_state_entry_round_trip():
    """Datetime fields should serialize to JSON-safe strings and restore back."""
    now = datetime.now()
    entry = {
        "domain": "example.xyz",
        "price": 1.99,
        "purchased_at": now,
        "expires_at": now + timedelta(days=365),
    }

    serialized = cli._serialize_domain_state_entry(entry)
    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    restored = cli._deserialize_domain_state_entry(serialized)
    assert isinstance(restored["purchased_at"], datetime)
    assert isinstance(restored["expires_at"], datetime)


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """Saving manager state should emit JSON with datetime strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_path)

    now = datetime.now()
    manager = SimpleNamespace(
        current_spending=2.5,
        active_domain="saved.xyz",
        owned_domains=[
            {
                "domain": "saved.xyz",
                "price": 2.5,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            }
        ],
    )
    config = {"api_key": "k", "api_secret": "s", "monthly_budget": 50.0}

    cli.save_manager_state(manager, config)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["active_domain"] == "saved.xyz"
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)


def test_build_parser_handles_new_subcommands_and_flags():
    """CLI parser should support new rotate and budget options."""
    parser = cli.build_parser()

    rotate_args = parser.parse_args(["rotate", "--yes", "--attempts", "4", "--max-price", "2.2"])
    assert rotate_args.command == "rotate"
    assert rotate_args.yes is True
    assert rotate_args.attempts == 4
    assert rotate_args.max_price == 2.2

    budget_args = parser.parse_args(["budget", "--set", "20"])
    assert budget_args.command == "budget"
    assert budget_args.set == 20
