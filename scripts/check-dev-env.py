#!/usr/bin/env python3
"""
Development Environment Check
Verifies required and optional dependencies for local development.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


CheckResult = Dict[str, object]


def make_result(
    check_id: str,
    name: str,
    ok: bool,
    required: bool,
    details: str,
    remediation: str,
) -> CheckResult:
    return {
        "id": check_id,
        "name": name,
        "ok": ok,
        "required": required,
        "details": details,
        "remediation": remediation,
    }


def check_python_version() -> CheckResult:
    current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 8)
    details = f"Python {current} detected"
    remediation = "Install Python 3.8+ and run this check again."
    return make_result("python-version", "Python Version", ok, True, details, remediation)


def check_command(command: str, display_name: str, required: bool, remediation: str) -> CheckResult:
    try:
        completed = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        version_line = (completed.stdout or completed.stderr).strip().splitlines()
        details = version_line[0] if version_line else f"{display_name} is installed"
        return make_result(f"cmd-{command}", display_name, True, required, details, remediation)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return make_result(
            f"cmd-{command}",
            display_name,
            False,
            required,
            f"{display_name} command not available",
            remediation,
        )


def check_python_module(module_name: str, display_name: str, required: bool, remediation: str) -> CheckResult:
    available = importlib.util.find_spec(module_name) is not None
    details = f"{display_name} importable" if available else f"{display_name} cannot be imported"
    return make_result(f"mod-{module_name}", display_name, available, required, details, remediation)


def check_path_exists(path: Path, display_name: str, required: bool, remediation: str) -> CheckResult:
    exists = path.exists()
    details = f"{display_name} exists at {path}" if exists else f"{display_name} missing at {path}"
    return make_result(f"path-{display_name}", display_name, exists, required, details, remediation)


def check_playwright(project_root: Path) -> CheckResult:
    playwright_bin = project_root / "node_modules" / ".bin" / "playwright"
    exists = playwright_bin.exists()
    details = (
        f"Playwright CLI found at {playwright_bin}"
        if exists
        else f"Playwright CLI missing at {playwright_bin}"
    )
    remediation = "Run npm install && npx playwright install"
    return make_result("node-playwright", "Playwright", exists, True, details, remediation)


def collect_checks(project_root: Path) -> List[CheckResult]:
    checks: List[CheckResult] = [check_python_version()]

    checks.extend(
        [
            check_command("git", "Git", True, "Install git via your system package manager."),
            check_command("node", "Node.js", True, "Install Node.js 16+."),
            check_command("npm", "npm", True, "Install npm with Node.js."),
            check_command("podman", "Podman", False, "Install Podman for preferred container workflows."),
            check_command("docker", "Docker", False, "Install Docker if your workflow depends on it."),
        ]
    )

    checks.extend(
        [
            check_python_module("flask", "Flask", True, "Run pip install -r requirements.txt"),
            check_python_module("stem", "Stem (Tor)", True, "Run pip install -r requirements.txt"),
            check_python_module("pytest", "pytest", False, "Run pip install -r requirements-dev.txt"),
        ]
    )

    checks.extend(
        [
            check_path_exists(
                project_root / "requirements.txt",
                "requirements.txt",
                True,
                "Restore requirements.txt from source control.",
            ),
            check_path_exists(
                project_root / "requirements-dev.txt",
                "requirements-dev.txt",
                True,
                "Restore requirements-dev.txt from source control.",
            ),
            check_path_exists(
                project_root / "package.json",
                "package.json",
                True,
                "Restore package.json from source control.",
            ),
            check_path_exists(
                project_root / "pytest.ini",
                "pytest.ini",
                True,
                "Restore pytest.ini from source control.",
            ),
            check_path_exists(
                project_root / "VERSION",
                "VERSION",
                True,
                "Restore VERSION from source control.",
            ),
            check_path_exists(
                project_root / ".venv",
                ".venv",
                True,
                "Run ./scripts/bootstrap-dev-environment.sh to create the virtual environment.",
            ),
            check_path_exists(
                project_root / "node_modules",
                "node_modules",
                True,
                "Run npm install from the project root.",
            ),
            check_playwright(project_root),
        ]
    )

    return checks


def generate_report(project_root: Path) -> Dict[str, object]:
    checks = collect_checks(project_root)
    failed_required = [item for item in checks if item["required"] and not item["ok"]]
    failed_optional = [item for item in checks if not item["required"] and not item["ok"]]
    return {
        "project_root": str(project_root),
        "required_checks_total": sum(1 for item in checks if item["required"]),
        "optional_checks_total": sum(1 for item in checks if not item["required"]),
        "failed_required_total": len(failed_required),
        "failed_optional_total": len(failed_optional),
        "ok": len(failed_required) == 0,
        "checks": checks,
    }


def render_text_report(report: Dict[str, object], quiet: bool = False) -> None:
    checks: List[CheckResult] = report["checks"]  # type: ignore[assignment]
    print("=" * 64)
    print("OpSecChat Development Environment Check")
    print("=" * 64)
    print(f"Project root: {report['project_root']}")
    print()

    for item in checks:
        status = "OK" if item["ok"] else ("FAIL" if item["required"] else "WARN")
        req = "required" if item["required"] else "optional"
        print(f"[{status}] {item['name']} ({req})")
        if not quiet:
            print(f"      {item['details']}")
        if not item["ok"]:
            print(f"      fix: {item['remediation']}")

    print()
    print("-" * 64)
    print(
        "Summary: "
        f"{report['failed_required_total']} required failures, "
        f"{report['failed_optional_total']} optional failures"
    )
    if report["ok"]:
        print("Environment status: READY")
        print("Next steps:")
        print("  python runserver.py")
        print("  npm test")
    else:
        print("Environment status: NOT READY")
        print("Run ./scripts/bootstrap-dev-environment.sh to repair common issues.")
    print("=" * 64)


def write_report_to_file(report: Dict[str, object], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def determine_exit_code(report: Dict[str, object], fail_on_optional: bool) -> int:
    if report["failed_required_total"] > 0:
        return 1
    if fail_on_optional and report["failed_optional_total"] > 0:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate OpSecChat development environment")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project root to evaluate (default: repository root).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print report as JSON.",
    )
    parser.add_argument(
        "--output",
        help="Write JSON report to a file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce text output detail.",
    )
    parser.add_argument(
        "--fail-on-optional",
        action="store_true",
        help="Return non-zero exit code when optional checks fail.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report = generate_report(project_root)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        render_text_report(report, quiet=args.quiet)

    if args.output:
        write_report_to_file(report, Path(args.output).resolve())

    return determine_exit_code(report, fail_on_optional=args.fail_on_optional)


if __name__ == "__main__":
    sys.exit(main())
