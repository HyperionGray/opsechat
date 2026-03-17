from pathlib import Path

from scripts import repo_hygiene_report


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_marker_hits_ignores_docs_and_bak(tmp_path: Path) -> None:
    write_file(tmp_path / "src" / "core.py", "value = 1  # TODO: wire this\n")
    write_file(tmp_path / "docs" / "notes.md", "TODO: documentation task\n")
    write_file(tmp_path / "bak" / "old.py", "raise NotImplementedError\n")

    hits = repo_hygiene_report.collect_marker_hits(tmp_path)

    assert len(hits) == 1
    assert hits[0].path == "src/core.py"
    assert hits[0].marker == "TODO"


def test_collect_duplicate_workflow_files(tmp_path: Path) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    write_file(workflow_dir / "ci.yml", "name: CI\n")
    write_file(workflow_dir / "ci.yaml", "name: CI duplicate\n")
    write_file(workflow_dir / "security.yml", "name: Security\n")

    duplicates = repo_hygiene_report.collect_duplicate_workflow_files(tmp_path)

    assert duplicates == {"ci": ["ci.yaml", "ci.yml"]}


def test_collect_deprecated_active_workflows(tmp_path: Path) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    write_file(workflow_dir / "auto-gpt5-implementation.yml", "name: legacy\n")
    write_file(workflow_dir / "ci.yml", "name: CI\n")

    stale = repo_hygiene_report.collect_deprecated_active_workflows(tmp_path)

    assert stale == ["auto-gpt5-implementation.yml"]
