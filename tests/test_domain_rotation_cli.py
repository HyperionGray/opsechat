"""Tests for domain_rotation_cli persistence and automation flags."""

import json
from datetime import datetime

import domain_rotation_cli as cli
from domain_manager import DomainRotationManager


class DummyClient:
    """Lightweight stand-in for API client initialization in tests."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    """Owned domain datetime fields should be persisted as ISO strings."""
    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    manager = DomainRotationManager(monthly_budget=50.0)
    manager.current_spending = 2.99
    manager.active_domain = "example.xyz"
    manager.owned_domains = [
        {
            "domain": "example.xyz",
            "price": 2.99,
            "purchased_at": datetime(2026, 3, 17, 9, 0, 0),
            "expires_at": datetime(2027, 3, 17, 9, 0, 0),
        }
    ]

    config = {"api_key": "key", "api_secret": "secret", "monthly_budget": 50.0}
    cli.save_manager_state(manager, config)

    raw = json.loads(config_file.read_text(encoding="utf-8"))
    owned = raw["owned_domains"][0]
    assert owned["purchased_at"] == "2026-03-17T09:00:00"
    assert owned["expires_at"] == "2027-03-17T09:00:00"


def test_get_manager_deserializes_datetimes(tmp_path, monkeypatch):
    """Saved ISO timestamps should be loaded back as datetime objects."""
    config_file = tmp_path / "domain_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(
            {
                "api_key": "key",
                "api_secret": "secret",
                "monthly_budget": 50.0,
                "current_spending": 1.25,
                "active_domain": "example.xyz",
                "owned_domains": [
                    {
                        "domain": "example.xyz",
                        "price": 1.25,
                        "purchased_at": "2026-03-17T09:00:00",
                        "expires_at": "2027-03-17T09:00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cli, "PorkbunAPIClient", DummyClient)

    manager, _ = cli.get_manager()
    owned = manager.owned_domains[0]
    assert isinstance(owned["purchased_at"], datetime)
    assert isinstance(owned["expires_at"], datetime)
    assert manager.active_domain == "example.xyz"
    assert manager.current_spending == 1.25


def test_rotate_domain_yes_skips_prompt(monkeypatch):
    """--yes mode should not call input and should save state."""

    class FakeManager:
        def __init__(self):
            self.active_domain = None
            self.max_price_seen = None
            self.current_spending = 0.0
            self.owned_domains = []

        def get_budget_status(self):
            return {
                "monthly_budget": 10.0,
                "current_spending": 0.0,
                "remaining": 10.0,
                "domains_owned": 0,
            }

        def find_cheap_available_domain(self, max_price=5.0, max_attempts=10):
            self.max_price_seen = max_price
            return {"domain": "test123.xyz", "price": 2.5}

        def purchase_domain_if_budget_allows(self, domain, price):
            self.active_domain = domain
            self.current_spending += price
            self.owned_domains.append({"domain": domain, "price": price})
            return True

    fake_manager = FakeManager()
    state_saved = {"called": False}

    monkeypatch.setattr(cli, "get_manager", lambda: (fake_manager, {}))
    monkeypatch.setattr(
        cli,
        "save_manager_state",
        lambda manager, config: state_saved.update({"called": True}),
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda _: (_ for _ in ()).throw(AssertionError("input should not be called")),
    )

    cli.rotate_domain(auto_confirm=True, max_price=3.0)

    assert fake_manager.max_price_seen == 3.0
    assert fake_manager.active_domain == "test123.xyz"
    assert state_saved["called"] is True
