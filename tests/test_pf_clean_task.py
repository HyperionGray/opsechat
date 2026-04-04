import importlib.util
from pathlib import Path
from types import SimpleNamespace


REPO_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_DIR / "pf-tasks" / "clean.py"


def _load_clean_module():
    spec = importlib.util.spec_from_file_location("pf_clean_task", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_determine_cleanup_method_defaults():
    clean = _load_clean_module()

    no_flags = SimpleNamespace(
        method=None,
        images=False,
        artifacts=False,
        repo_hygiene=False,
        repo_hygiene_fix=False,
    )
    assert clean.determine_cleanup_method(no_flags) == "all"

    artifacts_only = SimpleNamespace(
        method=None,
        images=False,
        artifacts=True,
        repo_hygiene=False,
        repo_hygiene_fix=False,
    )
    assert clean.determine_cleanup_method(artifacts_only) is None

    repo_hygiene_only = SimpleNamespace(
        method=None,
        images=False,
        artifacts=False,
        repo_hygiene=True,
        repo_hygiene_fix=False,
    )
    assert clean.determine_cleanup_method(repo_hygiene_only) is None

    repo_hygiene_fix_only = SimpleNamespace(
        method=None,
        images=False,
        artifacts=False,
        repo_hygiene=False,
        repo_hygiene_fix=True,
    )
    assert clean.determine_cleanup_method(repo_hygiene_fix_only) is None

    images_only = SimpleNamespace(
        method=None,
        images=True,
        artifacts=False,
        repo_hygiene=False,
        repo_hygiene_fix=False,
    )
    assert clean.determine_cleanup_method(images_only) == "all"

    explicit = SimpleNamespace(
        method="compose",
        images=False,
        artifacts=False,
        repo_hygiene=False,
        repo_hygiene_fix=False,
    )
    assert clean.determine_cleanup_method(explicit) == "compose"


def test_scan_repo_hygiene_detects_tracked_and_broken(monkeypatch, tmp_path):
    clean = _load_clean_module()

    tracked = ["Dockerfile~HEAD", ".bish-index", "src/main.py"]
    monkeypatch.setattr(clean, "_list_tracked_files", lambda _: tracked)

    live_target = tmp_path / "live.txt"
    live_target.write_text("ok", encoding="utf-8")
    live_link = tmp_path / "live-link"
    live_link.symlink_to(live_target)

    broken_link = tmp_path / "broken-link"
    broken_link.symlink_to(tmp_path / "missing-target")

    findings = clean.scan_repo_hygiene(tmp_path)

    assert findings["tracked_backups"] == ["Dockerfile~HEAD"]
    assert findings["tracked_bish_artifacts"] == [".bish-index"]
    assert findings["broken_symlinks"] == ["broken-link"]


def test_apply_repo_hygiene_fixes_removes_tracked_and_untracked(monkeypatch, tmp_path):
    clean = _load_clean_module()

    class Result:
        def __init__(self, returncode):
            self.returncode = returncode

    git_rm_calls = []

    def fake_run_command(cmd, cwd=None, check=True):
        git_rm_calls.append((cmd, cwd, check))
        return Result(0)

    monkeypatch.setattr(clean, "run_command", fake_run_command)

    broken_link = tmp_path / "broken-link"
    broken_link.symlink_to(tmp_path / "missing-target")
    assert broken_link.is_symlink()

    findings = {
        "tracked_backups": ["Dockerfile~HEAD"],
        "tracked_bish_artifacts": [],
        "broken_symlinks": ["broken-link"],
        "tracked_set": ["Dockerfile~HEAD"],
    }

    success = clean.apply_repo_hygiene_fixes(tmp_path, findings)

    assert success is True
    assert git_rm_calls[0][0] == ["git", "rm", "-f", "--", "Dockerfile~HEAD"]
    assert git_rm_calls[0][1] == tmp_path
    assert not broken_link.exists()

