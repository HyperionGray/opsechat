"""
Unit tests for scripts/release_readiness_check.py.
"""

from scripts.release_readiness_check import (
    scan_required_paths,
    scan_stale_files,
    scan_unfinished_markers,
)


def test_scan_required_paths_reports_missing_file(tmp_path):
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    findings = scan_required_paths(tmp_path, required_paths=["README.md", "VERSION"])

    assert len(findings) == 1
    assert findings[0].category == "required-path"
    assert findings[0].path == "VERSION"


def test_scan_unfinished_markers_detects_source_markers(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("print('x')\n# TODO fix this\n", encoding="utf-8")

    findings = scan_unfinished_markers(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "unfinished-marker"
    assert findings[0].path == "module.py"
    assert findings[0].line == 2


def test_scan_unfinished_markers_detects_js_markers(tmp_path):
    source_file = tmp_path / "app.js"
    source_file.write_text("const x = 1;\n// FIXME cleanup\n", encoding="utf-8")

    findings = scan_unfinished_markers(tmp_path)
    assert len(findings) == 1
    assert findings[0].path == "app.js"
    assert findings[0].line == 2


def test_scan_unfinished_markers_ignores_plain_text_tokens(tmp_path):
    source_file = tmp_path / "module.py"
    source_file.write_text("label = 'TODO item for docs'\n", encoding="utf-8")

    findings = scan_unfinished_markers(tmp_path)
    assert findings == []


def test_scan_unfinished_markers_ignores_non_source_files(tmp_path):
    note_file = tmp_path / "notes.md"
    note_file.write_text("TODO: documentation task\n", encoding="utf-8")

    findings = scan_unfinished_markers(tmp_path)
    assert findings == []


def test_scan_stale_files_detects_backup_artifacts(tmp_path):
    stale_file = tmp_path / "Dockerfile~HEAD"
    stale_file.write_text("old\n", encoding="utf-8")

    findings = scan_stale_files(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "stale-file"
    assert findings[0].path == "Dockerfile~HEAD"
