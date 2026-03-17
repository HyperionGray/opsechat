import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "rotate-domain.py"


def test_rotate_domain_cli_requires_credentials_for_actions():
    """CLI should fail fast with clear message when credentials are missing."""
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), "--list-owned"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={},
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert "Missing API credentials" in payload["error"]


def test_rotate_domain_cli_buy_requires_confirm_flag():
    """Purchases should require explicit --confirm to avoid accidents."""
    env = dict(os.environ)
    env["PORKBUN_API_KEY"] = "pk_test"
    env["PORKBUN_API_SECRET"] = "sk_test"

    result = subprocess.run(
        [sys.executable, str(CLI_PATH), "--buy", "example.xyz"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert "--confirm" in payload["error"]
