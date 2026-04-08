"""
Tests for rotate-domain.py CLI behavior.
"""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

from domain_manager import DomainAPIClient, DomainRotationManager


def _load_rotate_domain_module():
    module_path = Path(__file__).resolve().parents[1] / "rotate-domain.py"
    spec = importlib.util.spec_from_file_location("rotate_domain_cli", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cmd_search_available_returns_zero(capsys):
    module = _load_rotate_domain_module()
    mock_client = Mock(spec=DomainAPIClient)
    mock_client.search_domain.return_value = {"available": True, "price": "$2.99"}
    manager = DomainRotationManager(api_client=mock_client)

    result = module.cmd_search("example.xyz", manager)
    output = capsys.readouterr().out

    assert result == 0
    assert "AVAILABLE: example.xyz" in output


def test_cmd_buy_passes_total_and_years(monkeypatch):
    module = _load_rotate_domain_module()
    mock_client = Mock(spec=DomainAPIClient)
    mock_client.search_domain.return_value = {"available": True, "price": "$3.00"}
    manager = DomainRotationManager(api_client=mock_client, monthly_budget=20.0)

    calls = {}

    def fake_purchase(domain, price, years=1):
        calls["domain"] = domain
        calls["price"] = price
        calls["years"] = years
        return True

    monkeypatch.setattr(manager, "purchase_domain_if_budget_allows", fake_purchase)
    monkeypatch.setattr(module, "persist_manager_state", lambda _manager: None)

    result = module.cmd_buy("buyme.xyz", years=2, manager=manager)

    assert result == 0
    assert calls == {"domain": "buyme.xyz", "price": 6.0, "years": 2}
    assert manager.active_domain == "buyme.xyz"


def test_cmd_buy_rejects_when_budget_exceeded(monkeypatch):
    module = _load_rotate_domain_module()
    mock_client = Mock(spec=DomainAPIClient)
    mock_client.search_domain.return_value = {"available": True, "price": "$3.00"}
    manager = DomainRotationManager(api_client=mock_client, monthly_budget=5.0)

    purchase_spy = Mock(return_value=True)
    monkeypatch.setattr(manager, "purchase_domain_if_budget_allows", purchase_spy)

    result = module.cmd_buy("toolong.xyz", years=2, manager=manager)

    assert result == 2
    purchase_spy.assert_not_called()
