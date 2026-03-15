#!/usr/bin/env python3
"""
Tests for scripts/bootstrap-dev-environment.sh
"""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_SCRIPT = REPO_ROOT / "scripts" / "bootstrap-dev-environment.sh"


def run_bootstrap(*args: str) -> subprocess.CompletedProcess:
    """Run bootstrap script and return the completed process."""
    return subprocess.run(
        ["bash", str(BOOTSTRAP_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_bootstrap_script_exists():
    assert BOOTSTRAP_SCRIPT.exists(), "bootstrap script should exist"


def test_bootstrap_script_has_valid_syntax():
    result = subprocess.run(
        ["bash", "-n", str(BOOTSTRAP_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_bootstrap_help_output():
    result = run_bootstrap("--help")
    assert result.returncode == 0
    assert "Usage: ./scripts/bootstrap-dev-environment.sh" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--verify-only" in result.stdout


def test_bootstrap_dry_run_skip_heavy_steps():
    result = run_bootstrap(
        "--dry-run",
        "--skip-node",
        "--skip-tor",
        "--skip-playwright",
    )
    assert result.returncode == 0, result.stderr
    assert "[dry-run] mkdir -p" in result.stdout
    assert "Skipping Node.js setup per --skip-node" in result.stdout
    assert "Skipping Tor install per --skip-tor" in result.stdout


def test_bootstrap_verify_only_dry_run():
    result = run_bootstrap("--verify-only", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "check-dev-env.py" in result.stdout
