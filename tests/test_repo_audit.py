import importlib.util
from pathlib import Path


def _load_audit_module():
    module_path = Path(__file__).resolve().parent.parent / "pf-tasks" / "audit_repo.py"
    spec = importlib.util.spec_from_file_location("audit_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_detects_stale_backup_and_variant_files(tmp_path):
    audit = _load_audit_module()
    (tmp_path / "Dockerfile~HEAD").write_text("FROM alpine\n", encoding="utf-8")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "email_burner_old.html").write_text(
        "<html></html>\n", encoding="utf-8"
    )

    findings = audit.run_audit(tmp_path)
    found_kinds = {(item.kind, item.path) for item in findings}

    assert ("stale-backup-file", "Dockerfile~HEAD") in found_kinds
    assert ("stale-variant-file", "templates/email_burner_old.html") in found_kinds


def test_detects_duplicate_refactored_entrypoint(tmp_path):
    audit = _load_audit_module()
    (tmp_path / "runserver.py").write_text("print('same')\n", encoding="utf-8")
    (tmp_path / "runserver_refactored.py").write_text(
        "print('same')\n", encoding="utf-8"
    )

    findings = audit.run_audit(tmp_path)
    duplicates = [item for item in findings if item.kind == "duplicate-file-content"]

    assert duplicates
    assert duplicates[0].path == "runserver_refactored.py"


def test_apply_safe_fixes_only_removes_safe_items(tmp_path):
    audit = _load_audit_module()
    stale = tmp_path / "docker-compose.yml~HEAD"
    stale.write_text("services:\n", encoding="utf-8")
    regular = tmp_path / "runserver.py"
    regular.write_text("print('ok')\n", encoding="utf-8")

    findings = audit.run_audit(tmp_path)
    removed = audit.apply_safe_fixes(tmp_path, findings)

    assert "docker-compose.yml~HEAD" in removed
    assert not stale.exists()
    assert regular.exists()
