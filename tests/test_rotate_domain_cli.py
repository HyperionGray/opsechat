"""
Tests for rotate-domain.py flag-based CLI.
"""
import importlib.util
from pathlib import Path


def _load_rotate_domain_module():
    module_path = Path(__file__).resolve().parent.parent / "rotate-domain.py"
    spec = importlib.util.spec_from_file_location("rotate_domain_dash", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rotate_domain = _load_rotate_domain_module()


class TestRotateDomainCliHelpers:
    """Unit tests for helper behavior in rotate-domain.py."""

    def test_parse_price_parses_currency_string(self):
        assert rotate_domain.parse_price("$2.99") == 2.99
        assert rotate_domain.parse_price("€3.50") == 3.5

    def test_parse_price_handles_invalid_values(self):
        assert rotate_domain.parse_price(None) is None
        assert rotate_domain.parse_price("not-a-price") is None

    def test_resolve_credentials_prefers_arguments(self, monkeypatch):
        monkeypatch.setenv("PORKBUN_API_KEY", "env_key")
        monkeypatch.setenv("PORKBUN_SECRET_KEY", "env_secret")

        class Args:
            api_key = "arg_key"
            api_secret = "arg_secret"

        key, secret = rotate_domain.resolve_credentials(
            Args(), {"api_key": "cfg_key", "api_secret": "cfg_secret"}
        )
        assert key == "arg_key"
        assert secret == "arg_secret"

    def test_resolve_credentials_falls_back_to_config(self, monkeypatch):
        monkeypatch.delenv("PORKBUN_API_KEY", raising=False)
        monkeypatch.delenv("PORKBUN_SECRET_KEY", raising=False)

        class Args:
            api_key = None
            api_secret = None

        key, secret = rotate_domain.resolve_credentials(
            Args(), {"api_key": "cfg_key", "api_secret": "cfg_secret"}
        )
        assert key == "cfg_key"
        assert secret == "cfg_secret"

