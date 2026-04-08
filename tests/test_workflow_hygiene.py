import json
from pathlib import Path

from scripts.check_workflow_hygiene import check_workflow_hygiene


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_minimal_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path
    policy_path = repo_root / ".github" / "workflow-hygiene.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    return repo_root, policy_path


def test_hygiene_passes_with_template_backed_and_allowlisted_workflows(tmp_path):
    repo_root, policy_path = _setup_minimal_repo(tmp_path)
    policy_path.write_text(
        json.dumps(
            {
                "allowed_local_workflows": ["local-only.yml"],
                "required_template_workflows": ["required.yml"],
            }
        ),
        encoding="utf-8",
    )

    _write(repo_root / ".github/workflow-templates/required.yml", "name: required")
    _write(repo_root / ".github/workflows/required.yml", "name: required")
    _write(repo_root / ".github/workflows/local-only.yml", "name: local")

    result = check_workflow_hygiene(repo_root, policy_path)
    assert result.ok is True
    assert result.unmanaged_workflows == []
    assert result.missing_required_in_templates == []
    assert result.missing_required_in_workflows == []
    assert result.nested_workflow_entries == []


def test_hygiene_flags_unmanaged_and_missing_required_workflows(tmp_path):
    repo_root, policy_path = _setup_minimal_repo(tmp_path)
    policy_path.write_text(
        json.dumps(
            {
                "allowed_local_workflows": [],
                "required_template_workflows": ["required.yml"],
            }
        ),
        encoding="utf-8",
    )

    _write(repo_root / ".github/workflow-templates/optional.yml", "name: optional")
    _write(repo_root / ".github/workflows/unmanaged.yml", "name: unmanaged")

    result = check_workflow_hygiene(repo_root, policy_path)
    assert result.ok is False
    assert result.unmanaged_workflows == ["unmanaged.yml"]
    assert result.missing_required_in_templates == ["required.yml"]
    assert result.missing_required_in_workflows == ["required.yml"]


def test_hygiene_flags_nested_placeholder_directory_entries(tmp_path):
    repo_root, policy_path = _setup_minimal_repo(tmp_path)
    policy_path.write_text(
        json.dumps(
            {
                "allowed_local_workflows": [],
                "required_template_workflows": [],
            }
        ),
        encoding="utf-8",
    )

    _write(
        repo_root / ".github/.github/workflows/workflows-sync.yml",
        "# placeholder",
    )

    result = check_workflow_hygiene(repo_root, policy_path)
    assert result.ok is False
    assert result.nested_workflow_entries == [
        ".github/.github/workflows/workflows-sync.yml"
    ]
