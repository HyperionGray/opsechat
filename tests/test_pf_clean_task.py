"""
Tests for pf-tasks/clean.py repository hygiene helpers.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace


REPO_DIR = Path(__file__).resolve().parents[1]
CLEAN_TASK_PATH = REPO_DIR / "pf-tasks" / "clean.py"

spec = importlib.util.spec_from_file_location("pf_clean_task", CLEAN_TASK_PATH)
clean_task = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(clean_task)


def test_find_stale_files_detects_merge_artifacts(tmp_path):
    stale_one = tmp_path / "Dockerfile~HEAD"
    stale_two = tmp_path / "notes.orig"
    stale_one.write_text("stale", encoding="utf-8")
    stale_two.write_text("stale", encoding="utf-8")

    # These should be ignored by scan rules.
    skipped_git = tmp_path / ".git" / "ignored~HEAD"
    skipped_bak = tmp_path / "bak" / "ignored.orig"
    skipped_git.parent.mkdir(parents=True, exist_ok=True)
    skipped_bak.parent.mkdir(parents=True, exist_ok=True)
    skipped_git.write_text("ignored", encoding="utf-8")
    skipped_bak.write_text("ignored", encoding="utf-8")

    results = clean_task.find_stale_files(tmp_path)
    rel_results = {str(path.relative_to(tmp_path)) for path in results}

    assert "Dockerfile~HEAD" in rel_results
    assert "notes.orig" in rel_results
    assert ".git/ignored~HEAD" not in rel_results
    assert "bak/ignored.orig" not in rel_results


def test_find_redundant_directory_paths_detects_adjacent_names(tmp_path):
    (tmp_path / "src" / "src" / "feature").mkdir(parents=True)
    (tmp_path / "docs" / "api").mkdir(parents=True)

    results = clean_task.find_redundant_directory_paths(tmp_path)
    rel_results = {str(path.relative_to(tmp_path)) for path in results}

    assert "src/src" in rel_results
    assert "docs/api" not in rel_results


def test_find_deep_directories_uses_threshold(tmp_path):
    shallow = tmp_path / "a" / "b"
    deep = tmp_path / "a" / "b" / "c" / "d"
    shallow.mkdir(parents=True)
    deep.mkdir(parents=True)

    results = clean_task.find_deep_directories(tmp_path, max_depth_warning=2)
    rel_results = {str(path.relative_to(tmp_path)) for path in results}

    assert "a/b/c" in rel_results
    assert "a/b/c/d" in rel_results
    assert "a/b" not in rel_results


def test_remove_stale_files_deletes_files(tmp_path):
    stale = tmp_path / "docker-compose.yml~HEAD"
    stale.write_text("stale", encoding="utf-8")

    removed = clean_task.remove_stale_files([stale])
    assert removed == 1
    assert not stale.exists()


def test_determine_cleanup_method_preserves_current_behavior():
    assert clean_task.determine_cleanup_method(
        SimpleNamespace(
            method=None,
            artifacts=False,
            images=False,
            repo_hygiene=False,
            fix_repo_hygiene=False,
        )
    ) == "all"
    assert clean_task.determine_cleanup_method(
        SimpleNamespace(
            method=None,
            artifacts=True,
            images=False,
            repo_hygiene=False,
            fix_repo_hygiene=False,
        )
    ) is None
    assert clean_task.determine_cleanup_method(
        SimpleNamespace(
            method="compose",
            artifacts=True,
            images=False,
            repo_hygiene=False,
            fix_repo_hygiene=False,
        )
    ) == "compose"


def test_determine_cleanup_method_hygiene_scan_is_safe_by_default():
    assert clean_task.determine_cleanup_method(
        SimpleNamespace(
            method=None,
            artifacts=False,
            images=False,
            repo_hygiene=True,
            fix_repo_hygiene=False,
        )
    ) is None
