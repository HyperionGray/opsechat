#!/usr/bin/env python3
"""Unit tests for pf-tasks/repo_hygiene_audit.py."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "pf-tasks" / "repo_hygiene_audit.py"
SPEC = importlib.util.spec_from_file_location("repo_hygiene_audit", MODULE_PATH)
repo_hygiene_audit = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(repo_hygiene_audit)


def test_scan_detects_backup_and_bish_and_nested_paths(tmp_path):
    repo_root = tmp_path

    backup = repo_root / "Dockerfile~HEAD"
    backup.write_text("FROM scratch\n", encoding="utf-8")

    bish = repo_root / ".bish-index"
    bish.write_text("idx\n", encoding="utf-8")

    nested = repo_root / ".github" / ".github" / "workflows" / "workflows-sync.yml"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("# Placeholder workflow for workflows-sync.yml\n", encoding="utf-8")

    stray = repo_root / ".github" / "d"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("", encoding="utf-8")

    issues = repo_hygiene_audit.scan_repository(
        repo_root,
        [
            "Dockerfile~HEAD",
            ".bish-index",
            ".github/.github/workflows/workflows-sync.yml",
            ".github/d",
        ],
    )
    kinds = {(issue.kind, issue.path) for issue in issues}

    assert ("backup-file", "Dockerfile~HEAD") in kinds
    assert ("build-artifact", ".bish-index") in kinds
    assert ("nested-github-workflow", ".github/.github/workflows/workflows-sync.yml") in kinds
    assert ("placeholder-workflow", ".github/.github/workflows/workflows-sync.yml") in kinds
    assert ("empty-stray-file", ".github/d") in kinds


def test_apply_fixes_removes_files_and_empty_parent_dirs(tmp_path):
    repo_root = tmp_path
    target = repo_root / ".github" / ".github" / "workflows" / "placeholder.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Placeholder workflow for x\n", encoding="utf-8")

    issues = [
        repo_hygiene_audit.Issue(
            kind="placeholder-workflow",
            path=".github/.github/workflows/placeholder.yml",
            message="placeholder",
            fixable=True,
        )
    ]

    removed_count = repo_hygiene_audit.apply_fixes(repo_root, issues)

    assert removed_count == 1
    assert not target.exists()
    assert not (repo_root / ".github" / ".github" / "workflows").exists()


def test_scan_deduplicates_issue_kinds_for_same_file(tmp_path):
    repo_root = tmp_path
    file_path = repo_root / "Dockerfile~HEAD"
    file_path.write_text("FROM scratch\n", encoding="utf-8")

    issues = repo_hygiene_audit.scan_repository(repo_root, ["Dockerfile~HEAD", "Dockerfile~HEAD"])
    backup_issues = [issue for issue in issues if issue.kind == "backup-file"]

    assert len(backup_issues) == 1
