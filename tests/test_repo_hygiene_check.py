from pathlib import Path

from scripts.repo_hygiene_check import (
    find_backup_artifacts,
    find_root_test_scripts,
    find_unfinished_markers,
    run_checks,
)


def test_find_backup_artifacts_detects_head_backup(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    backup_file = tmp_path / "docker-compose.yml~HEAD"
    backup_file.write_text("services: {}", encoding="utf-8")

    issues = find_backup_artifacts(tmp_path)

    assert len(issues) == 1
    assert issues[0].check == "backup-artifact"
    assert issues[0].path == "docker-compose.yml~HEAD"


def test_find_unfinished_markers_detects_only_comment_markers(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    (tmp_path / "docs").mkdir()
    code_file = tmp_path / "main.py"
    code_file.write_text(
        "\n".join(
            [
                "# TODO: convert this into helper",
                'message = "TODO appears in code string and should not trigger"',
                "print(message)",
            ]
        ),
        encoding="utf-8",
    )

    issues = find_unfinished_markers(tmp_path)

    assert len(issues) == 1
    assert issues[0].check == "unfinished-marker"
    assert issues[0].line == 1


def test_find_unfinished_markers_ignores_minified_assets(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    (tmp_path / "docs").mkdir()
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    minified = static_dir / "bundle.min.js"
    minified.write_text("// TODO this is from vendor bundle", encoding="utf-8")

    issues = find_unfinished_markers(tmp_path)

    assert issues == []


def test_find_root_test_scripts_returns_warning(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    (tmp_path / "docs").mkdir()
    script_path = tmp_path / "test-ci-fix.js"
    script_path.write_text("console.log('ok')", encoding="utf-8")

    issues = find_root_test_scripts(tmp_path)

    assert len(issues) == 1
    assert issues[0].level == "warning"
    assert issues[0].path == "test-ci-fix.js"


def test_run_checks_reports_missing_required_top_level(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()

    issues = run_checks(tmp_path)
    missing = [issue.path for issue in issues if issue.check == "top-level-structure"]

    assert "docs" in missing
    assert "include" in missing
