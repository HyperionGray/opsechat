#!/usr/bin/env python3
"""
Development Environment Check
Verifies that all required dependencies are installed and accessible.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def check_command(cmd, name, required=True):
    """Check if a command is available."""
    try:
        completed = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            check=True,
            text=True,
        )
        details = completed.stdout.strip() or completed.stderr.strip() or "version detected"
        return {
            "name": name,
            "ok": True,
            "required": required,
            "details": details,
        }
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {
            "name": name,
            "ok": False,
            "required": required,
            "details": str(exc),
        }


def check_python_module(module, name, required=True):
    """Check if a Python module can be imported."""
    try:
        __import__(module)
        return {
            "name": name,
            "ok": True,
            "required": required,
            "details": f"import {module} succeeded",
        }
    except ImportError as exc:
        return {
            "name": name,
            "ok": False,
            "required": required,
            "details": str(exc),
        }


def check_file(filepath, name, required=True):
    """Check if a file exists."""
    exists = Path(filepath).exists()
    return {
        "name": name,
        "ok": exists,
        "required": required,
        "details": str(filepath),
    }


def collect_results(project_root):
    """Collect all environment checks and return structured data."""
    python_ok = sys.version_info >= (3, 8)
    checks = {
        "python": {
            "name": "Python >= 3.8",
            "ok": python_ok,
            "required": True,
            "details": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        "commands": [
            check_command("git", "Git"),
            check_command("node", "Node.js"),
            check_command("npm", "npm"),
            check_command("podman", "Podman", required=False),
            check_command("docker", "Docker", required=False),
        ],
        "python_modules": [
            check_python_module("flask", "Flask"),
            check_python_module("stem", "Stem (Tor)"),
            check_python_module("pytest", "pytest", required=False),
        ],
        "files": [
            check_file(project_root / "requirements.txt", "requirements.txt"),
            check_file(project_root / "requirements-dev.txt", "requirements-dev.txt"),
            check_file(project_root / "package.json", "package.json"),
            check_file(project_root / "pytest.ini", "pytest.ini"),
            check_file(project_root / "VERSION", "VERSION"),
        ],
        "node_environment": {
            "node_modules": check_file(project_root / "node_modules", "node_modules"),
            "playwright_binary": check_file(
                project_root / "node_modules/.bin/playwright",
                "Playwright binary",
            ),
        },
    }

    return checks


def status_label(ok):
    return "OK" if ok else "FAIL"


def print_check_group(title, checks):
    print(f"{title}:")
    for check in checks:
        print(f"  [{status_label(check['ok'])}] {check['name']}")
    print()


def print_text_report(results):
    print("=" * 60)
    print("OpSecChat Development Environment Check")
    print("=" * 60)
    print()

    print("Python Version Check:")
    python_check = results["python"]
    print(
        f"  [{status_label(python_check['ok'])}] "
        f"Python {python_check['details']} (>= 3.8 required)"
    )
    print()

    print_check_group("System Commands", results["commands"])
    print_check_group("Python Modules", results["python_modules"])
    print_check_group("Configuration Files", results["files"])

    print("Node.js Environment:")
    node_modules = results["node_environment"]["node_modules"]
    playwright_binary = results["node_environment"]["playwright_binary"]
    print(f"  [{status_label(node_modules['ok'])}] node_modules")
    print(f"  [{status_label(playwright_binary['ok'])}] Playwright binary")
    print()

    print("=" * 60)


def calculate_status(results, strict=False):
    """Determine pass/fail status."""
    failures = []
    checks = [results["python"]] + results["commands"] + results["python_modules"] + results["files"]
    checks.extend(results["node_environment"].values())

    for check in checks:
        if not check["ok"] and (check["required"] or strict):
            failures.append(check["name"])

    return {
        "ok": len(failures) == 0,
        "failures": failures,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check OpSecChat development environment dependencies."
    )
    parser.add_argument(
        "--project-root",
        default=Path(__file__).resolve().parent.parent,
        type=Path,
        help="Project root to validate (default: repository root).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if optional checks are missing.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = args.project_root.resolve()
    os.chdir(project_root)

    results = collect_results(project_root)
    status = calculate_status(results, strict=args.strict)

    report = {
        "project_root": str(project_root),
        "strict": args.strict,
        "status": status,
        "checks": results,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(results)
        if status["ok"]:
            print("Environment check passed.")
        else:
            print("Environment check failed.")
            print("Missing required items:")
            for failure in status["failures"]:
                print(f"  - {failure}")
        print("=" * 60)

    return 0 if status["ok"] else 1

if __name__ == '__main__':
    sys.exit(main())
