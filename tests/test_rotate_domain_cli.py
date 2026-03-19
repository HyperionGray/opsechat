"""
Tests for the rotate_domain CLI module.
"""

import json

import rotate_domain


def test_search_command_outputs_availability(monkeypatch, capsys):
    """Search command prints expected availability details."""
    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

        def search_domain(self, domain):
            return {
                "available": True,
                "price": "2.99",
                "currency": "USD",
                "domain": domain,
            }

    monkeypatch.setattr(rotate_domain, "PorkbunAPIClient", FakeClient)
    monkeypatch.setenv("PORKBUN_API_KEY", "test_key")
    monkeypatch.setenv("PORKBUN_SECRET_KEY", "test_secret")

    result = rotate_domain.main(["--search", "example.xyz"])
    output = capsys.readouterr().out

    assert result == 0
    assert "Domain: example.xyz" in output
    assert "Available: yes" in output
    assert "Price: 2.99 USD" in output


def test_buy_command_requires_yes_noninteractive(monkeypatch, capsys):
    """Buy command should require --yes in non-interactive mode."""
    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret
            self.purchase_calls = 0

        def search_domain(self, domain):
            return {"available": True, "price": "2.99", "currency": "USD"}

        def purchase_domain(self, domain, years=1):
            self.purchase_calls += 1
            return {"success": True, "domain": domain}

    monkeypatch.setattr(rotate_domain, "PorkbunAPIClient", FakeClient)
    monkeypatch.setenv("PORKBUN_API_KEY", "test_key")
    monkeypatch.setenv("PORKBUN_SECRET_KEY", "test_secret")
    monkeypatch.setattr(rotate_domain.sys.stdin, "isatty", lambda: False)

    result = rotate_domain.main(["--buy", "example.xyz"])
    output = capsys.readouterr().out

    assert result == 1
    assert "Refusing non-interactive purchase without --yes" in output


def test_buy_command_persists_state(monkeypatch, tmp_path, capsys):
    """Buy command persists budget and owned domain state."""
    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

        def search_domain(self, domain):
            return {"available": True, "price": "$2.50", "currency": "USD"}

        def purchase_domain(self, domain, years=1):
            return {"success": True, "domain": domain, "order_id": "ord123"}

    config_file = tmp_path / "domain_config.json"
    monkeypatch.setattr(rotate_domain, "CONFIG_FILE", config_file)
    monkeypatch.setattr(rotate_domain, "PorkbunAPIClient", FakeClient)
    monkeypatch.setenv("PORKBUN_API_KEY", "test_key")
    monkeypatch.setenv("PORKBUN_SECRET_KEY", "test_secret")
    monkeypatch.setenv("DOMAIN_BUDGET", "10")

    result = rotate_domain.main(["--buy", "fresh-example.xyz", "--years", "2", "--yes"])
    output = capsys.readouterr().out

    assert result == 0
    assert "Purchased and activated domain: fresh-example.xyz" in output
    assert config_file.exists()

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["current_spending"] == 2.5
    assert saved["active_domain"] == "fresh-example.xyz"
    assert len(saved["owned_domains"]) == 1
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)
