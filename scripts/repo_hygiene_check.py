#!/usr/bin/env python3
"""
Repository hygiene checks for ongoing cleanup automation.

This script focuses on practical drift signals:
1) merge/backup artifacts accidentally committed
2) unfinished TODO/FIXME/STUB markers in production code comments
3) obvious root-level scratch test scripts
4) expected top-level project structure
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


BACKUP_PATTERNS = ("**/*~HEAD", "**/*~", "**/*.orig", "**/*.rej")
CODE_SUFFIXES = {".py", ".sh", ".js", ".ts", ".tsx", ".jsx"}
MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|STUB|TBD|UNFINISHED)\b", re.IGNORECASE)
REQUIRED_TOP_LEVEL = ("docs", "src", "include")
GENERATED_FILE_SUFFIXES = (".min.js", ".min.ts", ".bundle.js")

IGNORED_PATH_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "docs",
    "tests",
    "bak",
    "dist",
    "build",
    "playwright-report",
    "test-results",
}


@dataclass(frozen=True)
class Issue:
    level: str
    check: str
    path: str
    message: str
    line: int | None = None


def _is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in path.parts)


def _is_comment_line(line: str, suffix: str) -> bool:
    stripped = line.lstrip()
    if suffix in {".py", ".sh"}:
        return stripped.startswith("#")
    if suffix in {".js", ".ts", ".tsx", ".jsx"}:
        return (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
        )
    return False


def _is_generated_asset(path: Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in GENERATED_FILE_SUFFIXES)


def find_backup_artifacts(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[Path] = set()

    for pattern in BACKUP_PATTERNS:
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            if candidate in seen:
                continue
            if _is_ignored_path(candidate.relative_to(root)):
                continue
            seen.add(candidate)
            issues.append(
                Issue(
                    level="error",
                    check="backup-artifact",
                    path=str(candidate.relative_to(root)),
                    message="Backup/merge artifact should be removed from repository",
                )
            )
    return sorted(issues, key=lambda item: item.path)


def find_unfinished_markers(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file() or file_path.suffix not in CODE_SUFFIXES:
            continue
        rel_path = file_path.relative_to(root)
        if _is_ignored_path(rel_path):
            continue
        if _is_generated_asset(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

        for line_number, line in enumerate(content.splitlines(), start=1):
            if not MARKER_PATTERN.search(line):
                continue
            if not _is_comment_line(line, file_path.suffix):
                continue
            issues.append(
                Issue(
                    level="error",
                    check="unfinished-marker",
                    path=str(rel_path),
                    line=line_number,
                    message="Unfinished marker found in production code comment",
                )
            )
    return sorted(issues, key=lambda item: (item.path, item.line or 0))


def find_root_test_scripts(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for candidate in root.glob("test-*.js"):
        if not candidate.is_file():
            continue
        issues.append(
            Issue(
                level="warning",
                check="root-clutter",
                path=str(candidate.relative_to(root)),
                message="Root test helper script should live under tests/manual or scripts/",
            )
        )
    return sorted(issues, key=lambda item: item.path)


def find_missing_required_top_level(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for name in REQUIRED_TOP_LEVEL:
        if not (root / name).exists():
            issues.append(
                Issue(
                    level="error",
                    check="top-level-structure",
                    path=name,
                    message=f"Required top-level path '{name}' is missing",
                )
            )
    return issues


def run_checks(root: Path) -> list[Issue]:
    checks: Iterable[list[Issue]] = (
        find_backup_artifacts(root),
        find_unfinished_markers(root),
        find_root_test_scripts(root),
        find_missing_required_top_level(root),
    )
    all_issues: list[Issue] = []
    for issue_list in checks:
        all_issues.extend(issue_list)
    return all_issues


def print_text_report(issues: list[Issue]) -> None:
    if not issues:
        print("Repository hygiene check passed: no issues found.")
        return

    print("Repository hygiene report:")
    for issue in issues:
        location = issue.path
        if issue.line is not None:
            location = f"{location}:{issue.line}"
        print(f"- [{issue.level}] {issue.check} {location} :: {issue.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks")
    parser.add_argument(
        "--root",
        default=".",
        help="Path to repository root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON report",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures in exit code",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues = run_checks(root)

    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        print_text_report(issues)

    has_error = any(issue.level == "error" for issue in issues)
    has_warning = any(issue.level == "warning" for issue in issues)
    if has_error or (args.strict and has_warning):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
