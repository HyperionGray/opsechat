"""
Tests for domain_rotation_cli automation flows.
"""

import json
from datetime import datetime

import domain_rotation_cli as cli


class _FakeManager:
    def __init__(self, remaining=10.0, rotate_result=None):
        self.current_spending = 0.0
        self.monthly_budget = 50.0
        self.active_domain = None
        self.owned_domains = []
        self._remaining = remaining
        self._rotate_result = rotate_result or {
            "success": True,
            "domain": "autodomain.xyz",
            "active_domain": "autodomain.xyz",
            "price": 2.0,
            "message": "ok",
        }
        self.rotate_calls = []

    def get_budget_status(self):
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self._remaining,
            "domains_owned": len(self.owned_domains),
        }

    def rotate_to_new_domain(self, max_price=5.0, max_attempts=10, tlds=None, length=8):
        self.rotate_calls.append(
            {
                "max_price": max_price,
                "max_attempts": max_attempts,
                "tlds": tlds,
                "length": length,
            }
        )
        if self._rotate_result.get("success"):
            price = float(self._rotate_result.get("price", 0))
            self.current_spending += price
            self._remaining -= price
            self.active_domain = self._rotate_result.get("active_domain")
            self.owned_domains.append(
                {
                    "domain": self._rotate_result.get("domain"),
                    "price": price,
                    "purchased_at": datetime.now(),
                }
            )
        return dict(self._rotate_result)


def test_parse_tlds_handles_whitespace_and_prefixes():
    parsed = cli._parse_tlds(" .XYZ, club, , online ")
    assert parsed == ["xyz", "club", "online"]


def test_get_manager_returns_none_without_credentials(monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda: {})
    manager, config = cli.get_manager(exit_on_error=False)

    assert manager is None
    assert config == {}


def test_rotate_domain_auto_success_json_and_state_persist(monkeypatch, capsys):
    manager = _FakeManager(remaining=8.0)
    persisted = {"called": False, "quiet": None}

    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {"k": "v"}))

    def _save_state(mgr, cfg, quiet=False):
        persisted["called"] = True
        persisted["quiet"] = quiet
        assert mgr is manager
        assert cfg == {"k": "v"}

    monkeypatch.setattr(cli, "save_manager_state", _save_state)

    rc = cli.rotate_domain_auto(
        max_price=5.0,
        max_attempts=12,
        tlds="xyz,club",
        length=9,
        json_output=True,
    )

    assert rc == 0
    assert persisted["called"] is True
    assert persisted["quiet"] is True
    assert manager.rotate_calls == [
        {"max_price": 5.0, "max_attempts": 12, "tlds": ["xyz", "club"], "length": 9}
    ]

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["success"] is True
    assert payload["tlds"] == ["xyz", "club"]
    assert payload["result"]["domain"] == "autodomain.xyz"


def test_rotate_domain_auto_budget_exhausted(monkeypatch):
    manager = _FakeManager(remaining=0.0)

    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {}))

    save_called = {"value": False}

    def _save_state(*args, **kwargs):
        save_called["value"] = True

    monkeypatch.setattr(cli, "save_manager_state", _save_state)

    rc = cli.rotate_domain_auto(max_price=5.0, json_output=False)

    assert rc == 1
    assert save_called["value"] is False
    assert manager.rotate_calls == []


def test_rotate_domain_auto_failure_does_not_persist(monkeypatch, capsys):
    manager = _FakeManager(
        remaining=7.0,
        rotate_result={"success": False, "message": "not found"},
    )
    save_called = {"value": False}

    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {}))

    def _save_state(*args, **kwargs):
        save_called["value"] = True

    monkeypatch.setattr(cli, "save_manager_state", _save_state)

    rc = cli.rotate_domain_auto(max_price=4.0, json_output=True)

    assert rc == 1
    assert save_called["value"] is False
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["result"]["message"] == "not found"


def test_rotate_domain_auto_caps_max_price_to_remaining_budget(monkeypatch):
    manager = _FakeManager(remaining=1.25)
    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {}))
    monkeypatch.setattr(cli, "save_manager_state", lambda *args, **kwargs: None)

    rc = cli.rotate_domain_auto(max_price=5.0, json_output=False)

    assert rc == 0
    assert manager.rotate_calls
    assert manager.rotate_calls[0]["max_price"] == 1.25


def test_rotate_domain_auto_rejects_non_positive_attempts(monkeypatch):
    manager = _FakeManager(remaining=10.0)
    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {}))
    monkeypatch.setattr(cli, "save_manager_state", lambda *args, **kwargs: None)

    rc = cli.rotate_domain_auto(max_attempts=0, json_output=False)

    assert rc == 1
    assert manager.rotate_calls == []


def test_rotate_domain_auto_rejects_non_positive_length(monkeypatch):
    manager = _FakeManager(remaining=10.0)
    monkeypatch.setattr(cli, "get_manager", lambda **kwargs: (manager, {}))
    monkeypatch.setattr(cli, "save_manager_state", lambda *args, **kwargs: None)

    rc = cli.rotate_domain_auto(length=0, json_output=False)

    assert rc == 1
    assert manager.rotate_calls == []
