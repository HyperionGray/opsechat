"""
Tests for domain_rotation_cli state handling and command behavior.
"""

from datetime import datetime, timedelta

import domain_rotation_cli as cli


def _minimal_config():
    return {
        "monthly_budget": 25.0,
        "api_key": "pk_test",
        "api_secret": "sk_test",
    }


def test_get_manager_migrates_legacy_state(monkeypatch):
    config = {
        **_minimal_config(),
        "current_spending": 3.5,
        "active_domain": "legacy.xyz",
        "owned_domains": [
            {
                "domain": "legacy.xyz",
                "price": 1.5,
                "purchased_at": "2026-03-01T00:00:00",
                "expires_at": "2027-03-01T00:00:00",
            }
        ],
    }

    monkeypatch.setattr(cli, "load_config", lambda: config)
    manager, loaded = cli.get_manager(require_api=False)

    assert loaded is config
    assert manager.active_domain == "legacy.xyz"
    assert manager.current_spending == 3.5
    assert len(manager.get_owned_domains()) == 1


def test_save_manager_state_writes_manager_state_and_legacy_keys(monkeypatch):
    manager = cli.DomainRotationManager(monthly_budget=25.0)
    manager.current_spending = 4.0
    manager.active_domain = "active.xyz"
    manager.owned_domains = [
        {
            "domain": "active.xyz",
            "price": 2.0,
            "purchased_at": datetime(2026, 4, 1, 9, 30, 0),
            "expires_at": datetime(2027, 4, 1, 9, 30, 0),
        }
    ]

    saved = {}

    def fake_save_config(cfg):
        saved["config"] = cfg.copy()

    monkeypatch.setattr(cli, "save_config", fake_save_config)
    config = {}
    cli.save_manager_state(manager, config)

    written = saved["config"]
    assert "manager_state" in written
    assert written["manager_state"]["active_domain"] == "active.xyz"
    assert written["active_domain"] == "active.xyz"
    assert written["current_spending"] == 4.0
    assert isinstance(written["owned_domains"][0]["purchased_at"], str)


def test_prune_domains_persists_updates(monkeypatch, capsys):
    now = datetime.now()
    manager = cli.DomainRotationManager(monthly_budget=10.0)
    manager.active_domain = "live.xyz"
    manager.owned_domains = [
        {
            "domain": "expired.xyz",
            "price": 1.0,
            "purchased_at": now - timedelta(days=500),
            "expires_at": now - timedelta(days=1),
        },
        {
            "domain": "live.xyz",
            "price": 1.5,
            "purchased_at": now - timedelta(days=10),
            "expires_at": now + timedelta(days=355),
        },
    ]

    state = {}

    monkeypatch.setattr(cli, "get_manager", lambda require_api=False: (manager, state))
    monkeypatch.setattr(cli, "save_manager_state", lambda m, c: c.update(m.export_state()))

    cli.prune_domains()
    output = capsys.readouterr().out

    assert "Expired domains removed: 1" in output
    assert state["active_domain"] == "live.xyz"
    assert len(state["owned_domains"]) == 1
