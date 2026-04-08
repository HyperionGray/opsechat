import importlib.util
import json
import subprocess
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "pf-tasks" / "hygiene.py"
SPEC = importlib.util.spec_from_file_location("pf_tasks_hygiene", MODULE_PATH)
HYGIENE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(HYGIENE)


def test_scan_unfinished_markers_ignores_docs(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()

    src = project / "src.py"
    src.write_text("x = 1  # TODO: implement\n", encoding="utf-8")

    docs = project / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("TODO in docs should be ignored\n", encoding="utf-8")

    findings = HYGIENE.scan_unfinished_markers(project)
    assert len(findings) == 1
    assert findings[0].path == "src.py"
    assert findings[0].line == 1


def test_scan_backup_files_and_cleanup(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()

    backup_one = project / "Dockerfile~HEAD"
    backup_one.write_text("stale\n", encoding="utf-8")
    backup_two = project / "patch.orig"
    backup_two.write_text("stale\n", encoding="utf-8")

    findings = HYGIENE.scan_backup_files(project)
    assert {f.path for f in findings} == {"Dockerfile~HEAD", "patch.orig"}

    removed = HYGIENE.cleanup_backup_files(project, findings)
    assert removed == 2
    assert not backup_one.exists()
    assert not backup_two.exists()


def test_build_json_payload_reports_counts(tmp_path: Path):
    findings = [
        HYGIENE.Finding("unfinished-marker", "a.py", 2, "TODO"),
        HYGIENE.Finding("backup-file", "Dockerfile~HEAD", None, "stale backup"),
    ]
    payload = HYGIENE.build_json_payload(tmp_path, findings)
    parsed = json.loads(payload)

    assert parsed["counts"]["unfinished-markers"] == 1
    assert parsed["counts"]["backup-files"] == 1
    assert parsed["counts"]["total"] == 2


def test_hygiene_script_passes_on_self_without_false_positives():
    result = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--strict", "--root", str(Path(__file__).resolve().parent.parent)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
