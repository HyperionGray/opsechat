#!/usr/bin/env python3
"""Tests for repository-hygiene behavior in pf-tasks/clean.py."""

import argparse
import importlib.util
from pathlib import Path


def load_clean_module():
    """Load pf-tasks/clean.py as a module for testing."""
    module_path = Path(__file__).resolve().parents[1] / "pf-tasks" / "clean.py"
    spec = importlib.util.spec_from_file_location("pf_clean", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_determine_cleanup_method_repo_only():
    """Repo-only cleanup should not trigger deployment cleanup."""
    clean = load_clean_module()
    args = argparse.Namespace(
        method=None,
        images=False,
        artifacts=False,
        repo=True,
        repo_dry_run=False,
    )
    assert clean.determine_cleanup_method(args) is None


def test_determine_cleanup_method_defaults_to_all():
    """Default behavior should still perform full cleanup."""
    clean = load_clean_module()
    args = argparse.Namespace(
        method=None,
        images=False,
        artifacts=False,
        repo=False,
        repo_dry_run=False,
    )
    assert clean.determine_cleanup_method(args) == "all"


def test_find_stale_repo_files_detects_and_ignores(tmp_path):
    """Detect stale files while ignoring ignored subtrees like .venv."""
    clean = load_clean_module()

    stale_file = tmp_path / "Dockerfile~HEAD"
    stale_file.write_text("backup", encoding="utf-8")

    ignored_dir = tmp_path / ".venv"
    ignored_dir.mkdir()
    ignored_stale = ignored_dir / ".bish-index"
    ignored_stale.write_text("ignored", encoding="utf-8")

    normal_file = tmp_path / "README.md"
    normal_file.write_text("normal", encoding="utf-8")

    found = clean.find_stale_repo_files(tmp_path)
    found_set = {path.resolve() for path in found}

    assert stale_file.resolve() in found_set
    assert ignored_stale.resolve() not in found_set
    assert normal_file.resolve() not in found_set
