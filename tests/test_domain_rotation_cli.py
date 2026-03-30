"""
Tests for domain_rotation_cli.py state loading/saving and prune flow.
"""
from datetime import datetime, timedelta

import domain_rotation_cli as cli


class DummyManager:
    """Minimal manager used to test CLI glue logic."""

    def __init__(self):
        self.current_spending = 0.0
        self.active_domain = None
        self.imported_records = []
        self.exported_records = []

    def import_owned_domains(self, records):
        self.imported_records = list(records)

    def export_owned_domains(self):
        return list(self.exported_records)


def test_save_manager_state_exports_serializable_domains():
    manager = DummyManager()
    manager.current_spending = 12.5
    manager.active_domain = "active.example"
    manager.exported_records = [
        {
            "domain": "active.example",
            "price": 1.99,
            "purchased_at": "2026-03-30T10:00:00",
            "expires_at": "2027-03-30T10:00:00",
        }
    ]
    config = {}

    cli.save_manager_state(manager, config)

    assert config["current_spending"] == 12.5
    assert config["active_domain"] == "active.example"
    assert config["owned_domains"][0]["domain"] == "active.example"


def test_get_manager_imports_owned_domains_and_parses_budget(monkeypatch):
    class DummyClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    created = {}

    class ManagerSpy:
        def __init__(self, api_client, monthly_budget):
            created["manager"] = self
            self.api_client = api_client
            self.monthly_budget = monthly_budget
            self.current_spending = 0.0
            self.active_domain = None
            self.imported = []

        def import_owned_domains(self, records):
            self.imported = list(records)

    config = {
        "api_key": "k",
        "api_secret": "s",
        "monthly_budget": "49.95",
        "current_spending": "2.99",
        "active_domain": "x.example",
        "owned_domains": [{"domain": "x.example"}],
    }

    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "PorkbunAPIClient", DummyClient)
    monkeypatch.setattr(cli, "DomainRotationManager", ManagerSpy)

    manager, returned_config = cli.get_manager()
    assert returned_config is config
    assert manager.monthly_budget == 49.95
    assert manager.current_spending == 2.99
    assert manager.active_domain == "x.example"
    assert manager.imported == [{"domain": "x.example"}]


def test_prune_domains_removes_expired_and_persists(monkeypatch, capsys):
    class PruneManager:
        def __init__(self):
            now = datetime.now()
            self._domains = [
                {
                    "domain": "expired.example",
                    "price": 1.0,
                    "purchased_at": now - timedelta(days=366),
                    "expires_at": now - timedelta(days=1),
                },
                {
                    "domain": "active.example",
                    "price": 2.0,
                    "purchased_at": now - timedelta(days=2),
                    "expires_at": now + timedelta(days=300),
                },
            ]
            self.pruned_called = False

        def get_owned_domains(self):
            return self._domains

        def prune_expired_domains(self, now=None):
            self.pruned_called = True
            self._domains = [d for d in self._domains if d["expires_at"] > now]
            return 1

    manager = PruneManager()
    config = {}
    calls = {"saved": 0}

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, config))
    monkeypatch.setattr(
        cli,
        "save_manager_state",
        lambda mgr, cfg: calls.__setitem__("saved", calls["saved"] + 1),
    )

    cli.prune_domains(assume_yes=True)
    out = capsys.readouterr().out

    assert manager.pruned_called is True
    assert calls["saved"] == 1
    assert "Pruned 1 expired record(s)." in out
