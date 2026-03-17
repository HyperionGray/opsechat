#!/usr/bin/env python3
"""Unit tests for pf-tasks/clean.py."""

import importlib.util
from pathlib import Path
from unittest.mock import patch


def load_clean_module():
    """Load pf-tasks/clean.py as a module for testing."""
    module_path = Path(__file__).resolve().parent.parent / "pf-tasks" / "clean.py"
    spec = importlib.util.spec_from_file_location("pf_clean", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_determine_cleanup_method_behavior():
    clean = load_clean_module()

    class Args:
        def __init__(self, method=None, artifacts=False, images=False):
            self.method = method
            self.artifacts = artifacts
            self.images = images

    assert clean.determine_cleanup_method(Args()) == "all"
    assert clean.determine_cleanup_method(Args(artifacts=True)) is None
    assert clean.determine_cleanup_method(Args(images=True)) == "all"
    assert clean.determine_cleanup_method(Args(method="compose", artifacts=True)) == "compose"


def test_run_command_dry_run_skips_subprocess():
    clean = load_clean_module()

    with patch.object(clean.subprocess, "run", side_effect=AssertionError("should not execute")):
        result = clean.run_command(["echo", "hello"], dry_run=True)

    assert result.returncode == 0
    assert result.stdout == ""


def test_remove_path_dry_run_keeps_file(tmp_path):
    clean = load_clean_module()
    target = tmp_path / "keep.txt"
    target.write_text("still here", encoding="utf-8")

    clean.remove_path(target, dry_run=True)

    assert target.exists()


def test_remove_path_removes_file(tmp_path):
    clean = load_clean_module()
    target = tmp_path / "delete.txt"
    target.write_text("remove me", encoding="utf-8")

    clean.remove_path(target, dry_run=False)

    assert not target.exists()
