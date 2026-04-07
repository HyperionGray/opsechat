import importlib.util
from argparse import Namespace
from pathlib import Path


def load_clean_module():
    module_path = Path(__file__).resolve().parent.parent / "pf-tasks" / "clean.py"
    spec = importlib.util.spec_from_file_location("pf_clean_task", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_determine_cleanup_method_selective_repo_scan():
    module = load_clean_module()
    args = Namespace(method=None, artifacts=False, repo=True, repo_apply=False, images=False)
    assert module.determine_cleanup_method(args) is None


def test_determine_cleanup_method_defaults_to_all():
    module = load_clean_module()
    args = Namespace(method=None, artifacts=False, repo=False, repo_apply=False, images=False)
    assert module.determine_cleanup_method(args) == "all"


def test_find_repo_hygiene_candidates_detects_expected_files(tmp_path):
    module = load_clean_module()

    (tmp_path / "Dockerfile~HEAD").write_text("stale", encoding="utf-8")
    (tmp_path / "patch.orig").write_text("stale", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip~HEAD").write_text("ignored", encoding="utf-8")

    def fake_is_tracked(_project_root, relative_path):
        return relative_path == "Dockerfile~HEAD"

    module.is_tracked_by_git = fake_is_tracked
    candidates = module.find_repo_hygiene_candidates(tmp_path)
    rel_paths = [item["relative_path"] for item in candidates]

    assert "Dockerfile~HEAD" in rel_paths
    assert "patch.orig" in rel_paths
    assert "node_modules/skip~HEAD" not in rel_paths

    tracked_map = {item["relative_path"]: item["tracked"] for item in candidates}
    assert tracked_map["Dockerfile~HEAD"] is True
    assert tracked_map["patch.orig"] is False


def test_clean_repository_hygiene_apply_removes_candidates(tmp_path):
    module = load_clean_module()
    stale_path = tmp_path / "docker-compose.yml~HEAD"
    stale_path.write_text("stale", encoding="utf-8")

    module.find_repo_hygiene_candidates = lambda _project_root: [
        {
            "path": stale_path,
            "relative_path": "docker-compose.yml~HEAD",
            "reason": "git merge backup artifact",
            "auto_remove": True,
            "tracked": True,
        }
    ]

    assert stale_path.exists()
    assert module.clean_repository_hygiene(apply=True) is True
    assert not stale_path.exists()
