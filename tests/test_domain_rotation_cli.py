"""
Tests for domain_rotation_cli automation-friendly command behavior.
"""
from unittest.mock import Mock

import pytest

import domain_rotation_cli as cli


def _manager_with_budget(remaining=20.0):
    manager = Mock()
    manager.get_budget_status.return_value = {
        "monthly_budget": 50.0,
        "current_spending": 50.0 - remaining,
        "remaining": remaining,
        "domains_owned": 1,
    }
    return manager


def test_rotate_domain_dry_run_does_not_purchase(monkeypatch):
    manager = _manager_with_budget(remaining=10.0)
    manager.find_cheap_available_domain.return_value = {
        "domain": "dryrun-example.xyz",
        "price": 2.25,
        "tld": "xyz",
    }
    manager.purchase_domain_if_budget_allows.side_effect = AssertionError(
        "purchase should not run during dry-run"
    )

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {}))
    result = cli.rotate_domain(dry_run=True, json_output=True)

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["candidate"]["domain"] == "dryrun-example.xyz"


def test_rotate_domain_yes_flag_purchases_without_prompt(monkeypatch):
    manager = _manager_with_budget(remaining=10.0)
    manager.find_cheap_available_domain.return_value = {
        "domain": "autoconfirm-example.xyz",
        "price": 2.5,
        "tld": "xyz",
    }
    manager.purchase_domain_if_budget_allows.return_value = {
        "success": True,
        "active_domain": "autoconfirm-example.xyz",
        "message": "Domain purchased successfully",
    }

    save_calls = []
    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {"saved": False}))
    monkeypatch.setattr(
        cli,
        "save_manager_state",
        lambda manager_obj, config_obj, quiet=False: save_calls.append((manager_obj, config_obj, quiet)),
    )
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(AssertionError("input should not be used")))

    result = cli.rotate_domain(auto_confirm=True)

    assert result["success"] is True
    manager.purchase_domain_if_budget_allows.assert_called_once_with("autoconfirm-example.xyz", 2.5)
    assert len(save_calls) == 1


def test_rotate_domain_cancelled_when_not_confirmed(monkeypatch):
    manager = _manager_with_budget(remaining=10.0)
    manager.find_cheap_available_domain.return_value = {
        "domain": "cancel-example.xyz",
        "price": 2.5,
        "tld": "xyz",
    }
    manager.purchase_domain_if_budget_allows.side_effect = AssertionError("purchase should not be attempted")

    monkeypatch.setattr(cli, "get_manager", lambda: (manager, {}))
    monkeypatch.setattr("builtins.input", lambda _: "no")

    result = cli.rotate_domain()

    assert result["success"] is False
    assert result["message"] == "Purchase cancelled."


def test_main_rotate_yes_dry_run_returns_success(monkeypatch):
    monkeypatch.setattr(cli, "rotate_domain", lambda **kwargs: {"success": True, "dry_run": kwargs["dry_run"]})
    code = cli.main(["rotate", "--yes", "--dry-run", "--json"])
    assert code == 0


def test_main_rejects_invalid_limits():
    with pytest.raises(SystemExit):
        cli.main(["search", "--limit", "0"])
