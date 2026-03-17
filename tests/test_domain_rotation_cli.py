import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import domain_rotation_cli


def test_save_manager_state_serializes_datetimes(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    manager = domain_rotation_cli.DomainRotationManager(
        api_client=Mock(), monthly_budget=25.0
    )
    manager.current_spending = 3.25
    manager.active_domain = "alpha.xyz"
    manager.owned_domains = [
        {
            "domain": "alpha.xyz",
            "price": 3.25,
            "purchased_at": datetime(2026, 1, 5, 12, 0, 0),
            "expires_at": datetime(2027, 1, 5, 12, 0, 0),
        }
    ]

    config = {"api_key": "k", "api_secret": "s", "monthly_budget": 25.0}
    domain_rotation_cli.save_manager_state(manager, config)

    saved = json.loads(config_path.read_text())
    owned = saved["owned_domains"][0]
    assert owned["domain"] == "alpha.xyz"
    assert isinstance(owned["purchased_at"], str)
    assert isinstance(owned["expires_at"], str)


def test_get_manager_restores_datetime_objects(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    domain_rotation_cli.save_config(
        {
            "api_key": "k",
            "api_secret": "s",
            "monthly_budget": 20.0,
            "current_spending": 1.5,
            "active_domain": "burn.xyz",
            "owned_domains": [
                {
                    "domain": "burn.xyz",
                    "price": 1.5,
                    "purchased_at": "2026-02-03T01:02:03",
                    "expires_at": "2027-02-03T01:02:03",
                }
            ],
        }
    )

    with patch("domain_rotation_cli.PorkbunAPIClient", return_value=Mock()):
        manager, _ = domain_rotation_cli.get_manager()

    assert manager.current_spending == 1.5
    assert manager.active_domain == "burn.xyz"
    assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)
    assert isinstance(manager.owned_domains[0]["expires_at"], datetime)


def test_list_domains_handles_legacy_string_dates(tmp_path, monkeypatch):
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    domain_rotation_cli.save_config(
        {
            "api_key": "k",
            "api_secret": "s",
            "owned_domains": [
                {
                    "domain": "legacy.xyz",
                    "price": 2.0,
                    "purchased_at": "2026-01-01T00:00:00",
                    "expires_at": "not-a-date",
                }
            ],
            "active_domain": "legacy.xyz",
        }
    )

    with patch("domain_rotation_cli.PorkbunAPIClient", return_value=Mock()):
        domain_rotation_cli.list_domains()


def test_rotate_domain_cli_help():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "rotate-domain.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--search" in result.stdout
    assert "--buy" in result.stdout


def test_rotate_domain_cli_invalid_years():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "rotate-domain.py", "--buy", "example.xyz", "--years", "0"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--years must be >= 1" in result.stdout
