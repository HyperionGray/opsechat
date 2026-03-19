from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repo_hygiene_check.py"
SPEC = spec_from_file_location("repo_hygiene_check", MODULE_PATH)
repo_hygiene_check = module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(repo_hygiene_check)


def test_clean_repo_has_no_hygiene_issues(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("print('ready')\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\n", encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert issues == []


def test_unfinished_markers_in_code_are_reported(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "build.sh").write_text(
        "# TODO: implement build\n", encoding="utf-8"
    )

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "NOTES.md").write_text(
        "# TODO (docs should be ignored)\n", encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert any("scripts/build.sh:1" in issue for issue in issues)
    assert all("docs/NOTES.md" not in issue for issue in issues)


def test_placeholder_workflow_is_reported(tmp_path):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "sample.yml").write_text(
        "# Placeholder workflow for sample.yml\n", encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert any(".github/workflows/sample.yml" in issue for issue in issues)


def test_nested_workflow_directory_is_reported(tmp_path):
    nested_dir = tmp_path / ".github" / ".github" / "workflows"
    nested_dir.mkdir(parents=True)
    (nested_dir / "sync.yml").write_text("name: nested\n", encoding="utf-8")

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert any(".github/.github/workflows/sync.yml" in issue for issue in issues)


def test_marker_keywords_in_non_comment_text_are_ignored(tmp_path):
    (tmp_path / "amazon_q_config.yaml").write_text(
        'patterns:\n  - "TODO:"\n  - "FIXME:"\n', encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert issues == []


def test_minified_javascript_files_are_ignored(tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "openpgp.min.js").write_text(
        "var a='STUB';\n", encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert issues == []


def test_python_string_containing_hash_todo_is_ignored(tmp_path):
    (tmp_path / "example.py").write_text(
        'text = "# TODO: this is string data"\n', encoding="utf-8"
    )

    issues = repo_hygiene_check.run_hygiene_checks(tmp_path)
    assert issues == []
