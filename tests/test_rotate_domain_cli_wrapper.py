"""
Tests for rotate-domain.py compatibility wrapper.
"""
import importlib.util
from pathlib import Path


def _load_rotate_domain_module():
    module_path = Path(__file__).resolve().parents[1] / "rotate-domain.py"
    spec = importlib.util.spec_from_file_location("rotate_domain_wrapper", str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args_requires_one_action():
    module = _load_rotate_domain_module()
    args = module._parse_args(["--search"])
    assert args.search is True
    assert args.buy is None


def test_main_dispatches_to_search(monkeypatch):
    module = _load_rotate_domain_module()
    called = {}

    def fake_run_command(command, auto_confirm=False):
        called["command"] = command
        called["auto_confirm"] = auto_confirm

    monkeypatch.setattr(module.cli, "run_command", fake_run_command)
    exit_code = module.main(["--search"])
    assert exit_code == 0
    assert called["command"] == "search"
    assert called["auto_confirm"] is False


def test_get_pricing_uses_domain_cli_manager(monkeypatch):
    module = _load_rotate_domain_module()

    class DummyClient:
        def get_pricing(self, tld):
            return {"tld": tld, "registration": "1.99", "renewal": "9.99", "transfer": "9.99"}

    class DummyManager:
        api_client = DummyClient()

    monkeypatch.setattr(module.cli, "get_manager", lambda: (DummyManager(), {}))
    exit_code = module.main(["--get-pricing", "xyz"])
    assert exit_code == 0


def test_buy_passes_years(monkeypatch):
    module = _load_rotate_domain_module()

    called = {}

    class DummyClient:
        def search_domain(self, domain):
            return {"available": True, "price": "1.99"}

    class DummyManager:
        api_client = DummyClient()
        active_domain = None

        def purchase_domain_if_budget_allows(self, domain, price, years=1):
            called["domain"] = domain
            called["price"] = price
            called["years"] = years
            return True

    monkeypatch.setattr(module.cli, "get_manager", lambda: (DummyManager(), {}))
    monkeypatch.setattr(module.cli, "save_manager_state", lambda _manager, _config: None)
    exit_code = module.main(["--buy", "example.xyz", "--years", "2", "--yes"])
    assert exit_code == 0
    assert called["domain"] == "example.xyz"
    assert called["years"] == 2


def test_years_rejected_without_buy():
    module = _load_rotate_domain_module()
    exit_code = module.main(["--search", "--years", "2"])
    assert exit_code == 1
