#!/usr/bin/env python3
"""Unit tests for pf-tasks/clean.py repository hygiene mode."""

import argparse
import importlib.util
from pathlib import Path


def _load_clean_module():
    clean_path = Path(__file__).resolve().parents[1] / "pf-tasks" / "clean.py"
    spec = importlib.util.spec_from_file_location("pf_clean", clean_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repo_hygiene_does_not_implicitly_clean_deployments():
    clean = _load_clean_module()
    args = argparse.Namespace(
        method=None,
        artifacts=False,
        images=False,
        repo_hygiene=True,
        apply_repo_cleanup=False,
    )
    assert clean.determine_cleanup_method(args) is None


def test_artifact_and_stale_duplicate_detection(tmp_path):
    clean = _load_clean_module()

    (tmp_path / ".bish-index").write_text("artifact", encoding="utf-8")
    (tmp_path / "runserver.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "runserver_refactored.py").write_text("print('ok')\n", encoding="utf-8")

    artifacts = clean.find_artifact_files(tmp_path)
    stale = clean.find_stale_duplicates(tmp_path)

    assert any(path.name == ".bish-index" for path in artifacts)
    assert any(path.name == "runserver_refactored.py" for path in stale)


def test_run_repository_hygiene_apply_removes_artifacts(tmp_path):
    clean = _load_clean_module()

    artifact = tmp_path / ".bish.sqlite"
    artifact.write_text("artifact", encoding="utf-8")
    canonical = tmp_path / "runserver.py"
    stale = tmp_path / "runserver_refactored.py"
    canonical.write_text("print('same')\n", encoding="utf-8")
    stale.write_text("print('same')\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("# TODO: later\n", encoding="utf-8")

    cleanup_ok, marker_hits = clean.run_repository_hygiene(tmp_path, apply=True, include_docs=False)

    assert cleanup_ok
    assert not artifact.exists()
    assert not stale.exists()
    assert marker_hits, "Expected TODO marker to be reported"
