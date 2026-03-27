"""
Tests for domain_rotation_cli behavior and state persistence.
"""

from datetime import datetime

import domain_rotation_cli as cli


def test_serialize_deserialize_domain_entry_round_trip():
    entry = {
        "domain": "example.xyz",
        "price": 1.99,
        "purchased_at": datetime(2026, 3, 27, 12, 0, 0),
        "expires_at": datetime(2027, 3, 27, 12, 0, 0),
    }

    serialized = cli._serialize_domain_entry(entry)

    assert isinstance(serialized["purchased_at"], str)
    assert isinstance(serialized["expires_at"], str)

    restored = cli._deserialize_domain_entry(serialized)
    assert isinstance(restored["purchased_at"], datetime)
    assert isinstance(restored["expires_at"], datetime)
    assert restored["domain"] == "example.xyz"


def test_save_manager_state_serializes_datetimes():
    class FakeManager:
        current_spending = 2.5
        active_domain = "example.xyz"
        owned_domains = [
            {
                "domain": "example.xyz",
                "price": 2.5,
                "purchased_at": datetime(2026, 3, 27, 12, 0, 0),
                "expires_at": datetime(2027, 3, 27, 12, 0, 0),
            }
        ]

    config = {}
    captured = {}

    def fake_save_config(cfg, silent=False):
        captured["cfg"] = cfg

    original_save = cli.save_config
    try:
        cli.save_config = fake_save_config
        cli.save_manager_state(FakeManager(), config)
    finally:
        cli.save_config = original_save

    saved = captured["cfg"]
    assert saved["current_spending"] == 2.5
    assert saved["active_domain"] == "example.xyz"
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)


def test_get_manager_uses_env_credentials(monkeypatch):
    monkeypatch.setenv("PORKBUN_API_KEY", "env-key")
    monkeypatch.setenv("PORKBUN_SECRET_KEY", "env-secret")
    monkeypatch.setenv("DOMAIN_BUDGET", "12.5")

    monkeypatch.setattr(cli, "load_config", lambda: {})

    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    class FakeManager:
        def __init__(self, api_client, monthly_budget):
            self.api_client = api_client
            self.monthly_budget = monthly_budget
            self.current_spending = 0.0
            self.owned_domains = []
            self.active_domain = None

    monkeypatch.setattr(cli, "PorkbunAPIClient", FakeClient)
    monkeypatch.setattr(cli, "DomainRotationManager", FakeManager)

    manager, config = cli.get_manager()
    assert manager.api_client.api_key == "env-key"
    assert manager.api_client.api_secret == "env-secret"
    assert manager.monthly_budget == 12.5
    assert config == {}


def test_config_non_interactive_requires_values(monkeypatch, capsys):
    class Args:
        api_key = None
        api_secret = None
        monthly_budget = None
        non_interactive = True

    try:
        cli.configure_api(Args())
        assert False, "Expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 1

    output = capsys.readouterr().out
    assert "No values provided for non-interactive config." in output
