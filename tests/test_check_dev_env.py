import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check-dev-env.py"


def load_check_dev_env_module():
    spec = importlib.util.spec_from_file_location("check_dev_env", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_report_counts_required_and_optional_failures(monkeypatch, tmp_path):
    module = load_check_dev_env_module()
    fake_checks = [
        {
            "id": "required-ok",
            "name": "Required OK",
            "ok": True,
            "required": True,
            "details": "",
            "remediation": "",
        },
        {
            "id": "required-fail",
            "name": "Required FAIL",
            "ok": False,
            "required": True,
            "details": "",
            "remediation": "",
        },
        {
            "id": "optional-fail",
            "name": "Optional FAIL",
            "ok": False,
            "required": False,
            "details": "",
            "remediation": "",
        },
    ]
    monkeypatch.setattr(module, "collect_checks", lambda _project_root: fake_checks)

    report = module.generate_report(tmp_path)

    assert report["required_checks_total"] == 2
    assert report["optional_checks_total"] == 1
    assert report["failed_required_total"] == 1
    assert report["failed_optional_total"] == 1
    assert report["ok"] is False


def test_determine_exit_code_respects_fail_on_optional():
    module = load_check_dev_env_module()

    report = {
        "failed_required_total": 0,
        "failed_optional_total": 1,
    }
    assert module.determine_exit_code(report, fail_on_optional=False) == 0
    assert module.determine_exit_code(report, fail_on_optional=True) == 1


def test_check_playwright_detects_local_cli(tmp_path):
    module = load_check_dev_env_module()
    (tmp_path / "node_modules" / ".bin").mkdir(parents=True)

    missing = module.check_playwright(tmp_path)
    assert missing["ok"] is False

    playwright_bin = tmp_path / "node_modules" / ".bin" / "playwright"
    playwright_bin.write_text("#!/bin/sh\n", encoding="utf-8")

    present = module.check_playwright(tmp_path)
    assert present["ok"] is True


def test_write_report_to_file_writes_valid_json(tmp_path):
    module = load_check_dev_env_module()
    report = {
        "project_root": str(tmp_path),
        "required_checks_total": 0,
        "optional_checks_total": 0,
        "failed_required_total": 0,
        "failed_optional_total": 0,
        "ok": True,
        "checks": [],
    }
    output_file = tmp_path / "reports" / "dev-env.json"

    module.write_report_to_file(report, output_file)

    assert output_file.exists()
    parsed = json.loads(output_file.read_text(encoding="utf-8"))
    assert parsed["ok"] is True
