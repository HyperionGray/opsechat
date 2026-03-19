import importlib.util
from pathlib import Path


def _load_repo_hygiene_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "repo_hygiene.py"
    spec = importlib.util.spec_from_file_location("repo_hygiene", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_detects_unfinished_markers(tmp_path):
    module = _load_repo_hygiene_module()
    source_file = tmp_path / "example.py"
    unfinished_token = "TO" + "DO:"
    source_file.write_text(
        f"print('hello')\n# {unfinished_token} finish\n",
        encoding="utf-8",
    )

    findings = module.scan_repository(tmp_path, fix=False)
    categories = [item.category for item in findings]
    assert "unfinished_marker" in categories


def test_fix_removes_bish_and_nested_placeholders(tmp_path):
    module = _load_repo_hygiene_module()

    bish_index = tmp_path / "tests" / ".bish-index"
    bish_index.parent.mkdir(parents=True, exist_ok=True)
    bish_index.write_text("stale\n", encoding="utf-8")

    nested_workflow = (
        tmp_path
        / ".github"
        / ".github"
        / "workflows"
        / "workflows-sync.yml"
    )
    nested_workflow.parent.mkdir(parents=True, exist_ok=True)
    nested_workflow.write_text(
        "# Placeholder workflow for workflows-sync.yml\n",
        encoding="utf-8",
    )

    findings = module.scan_repository(tmp_path, fix=True)

    assert not bish_index.exists()
    assert not nested_workflow.exists()
    assert all(item.fixed for item in findings)


def test_detects_refactor_duplicates(tmp_path):
    module = _load_repo_hygiene_module()

    (tmp_path / "mock_server.py").write_text("print('base')\n", encoding="utf-8")
    (tmp_path / "mock_server_refactored.py").write_text(
        "print('refactor')\n",
        encoding="utf-8",
    )

    findings = module.scan_repository(tmp_path, fix=False)
    categories = [item.category for item in findings]
    assert "stale_refactor_duplicate" in categories
