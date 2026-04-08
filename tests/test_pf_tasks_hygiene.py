import importlib.util
import pathlib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
HYGIENE_PATH = REPO_ROOT / "pf-tasks" / "hygiene.py"


def load_hygiene_module():
    spec = importlib.util.spec_from_file_location("pf_hygiene", HYGIENE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_scan_repo_is_clean_for_current_tree():
    hygiene = load_hygiene_module()
    findings = hygiene.scan_repo(REPO_ROOT)
    assert findings == []


def test_strict_mode_returns_nonzero_when_findings(tmp_path):
    hygiene = load_hygiene_module()
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "EXTRA.md").write_text("unexpected\n", encoding="utf-8")

    exit_code = hygiene.main(["--strict", "--root", str(tmp_path)])
    assert exit_code == 1


def test_cleanup_backups_removes_root_backup_files(tmp_path):
    hygiene = load_hygiene_module()
    backup_file = tmp_path / "docker-compose.yml~HEAD"
    backup_file.write_text("stale\n", encoding="utf-8")

    removed = hygiene.cleanup_backup_artifacts(tmp_path)
    assert removed == ["docker-compose.yml~HEAD"]
    assert not backup_file.exists()
