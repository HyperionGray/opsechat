"""
Tests for rotate-domain.py simple CLI wrapper.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "rotate-domain.py"
    spec = importlib.util.spec_from_file_location("rotate_domain_cli", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_price_handles_strings_numbers_and_invalid():
    cli = _load_module()

    assert cli.parse_price("2.99") == 2.99
    assert cli.parse_price("$4.50") == 4.5
    assert cli.parse_price(3) == 3.0
    assert cli.parse_price(None) is None
    assert cli.parse_price("not-a-price") is None


def test_resolve_credentials_prefers_args_then_env_then_config(monkeypatch):
    cli = _load_module()

    args = SimpleNamespace(api_key="arg-key", api_secret="arg-secret")
    key, secret = cli.resolve_credentials(args, {"api_key": "cfg-k", "api_secret": "cfg-s"})
    assert key == "arg-key"
    assert secret == "arg-secret"

    args = SimpleNamespace(api_key=None, api_secret=None)
    monkeypatch.setenv("PORKBUN_API_KEY", "env-key")
    monkeypatch.setenv("PORKBUN_API_SECRET", "env-secret")
    key, secret = cli.resolve_credentials(args, {"api_key": "cfg-k", "api_secret": "cfg-s"})
    assert key == "env-key"
    assert secret == "env-secret"

    monkeypatch.delenv("PORKBUN_API_KEY")
    monkeypatch.delenv("PORKBUN_API_SECRET")
    key, secret = cli.resolve_credentials(args, {"api_key": "cfg-k", "api_secret": "cfg-s"})
    assert key == "cfg-k"
    assert secret == "cfg-s"


def test_main_search_success(monkeypatch, capsys):
    cli = _load_module()

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_domain(self, domain):
            return {"domain": domain, "available": True, "price": "2.99", "currency": "USD"}

    monkeypatch.setattr(cli, "PorkbunAPIClient", FakeClient)
    monkeypatch.setattr(cli, "load_config", lambda: {"api_key": "k", "api_secret": "s"})

    rc = cli.main(["--search", "example.xyz"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Domain: example.xyz" in out
    assert "Available: yes" in out


def test_main_buy_blocked_by_budget(monkeypatch, capsys):
    cli = _load_module()
    state = {"purchase_called": False}

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_domain(self, _domain):
            return {"available": True, "price": "2.00", "currency": "USD"}

        def purchase_domain(self, _domain, years=1):
            state["purchase_called"] = True
            return {"success": True, "order_id": "x", "years": years}

    monkeypatch.setattr(cli, "PorkbunAPIClient", FakeClient)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: {
            "api_key": "k",
            "api_secret": "s",
            "monthly_budget": 5.0,
            "current_spending": 4.0,
        },
    )

    rc = cli.main(["--buy", "example.xyz", "--yes"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "Purchase blocked by budget policy" in out
    assert state["purchase_called"] is False


def test_main_buy_success_persists_spending(monkeypatch, capsys):
    cli = _load_module()
    state = {"saved": None}

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_domain(self, _domain):
            return {"available": True, "price": "2.99", "currency": "USD"}

        def purchase_domain(self, domain, years=1):
            return {"success": True, "order_id": "order-123", "domain": domain, "years": years}

    config = {
        "api_key": "k",
        "api_secret": "s",
        "monthly_budget": 10.0,
        "current_spending": 1.0,
    }
    monkeypatch.setattr(cli, "PorkbunAPIClient", FakeClient)
    monkeypatch.setattr(cli, "load_config", lambda: config.copy())
    monkeypatch.setattr(cli, "save_config", lambda payload: state.update({"saved": payload.copy()}))

    rc = cli.main(["--buy", "example.xyz", "--yes", "--years", "2"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Purchase successful for example.xyz" in out
    assert state["saved"] is not None
    assert state["saved"]["current_spending"] == 3.99


def test_main_list_owned_missing_credentials(monkeypatch, capsys):
    cli = _load_module()

    monkeypatch.setattr(cli, "load_config", lambda: {})
    monkeypatch.delenv("PORKBUN_API_KEY", raising=False)
    monkeypatch.delenv("PORKBUN_API_SECRET", raising=False)

    rc = cli.main(["--list-owned"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "Missing Porkbun API credentials" in out

