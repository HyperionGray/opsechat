#!/usr/bin/env python3
"""
PF Task: Repository hygiene checks for docs and stale artifacts.
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_ROOT_MARKDOWN = {
    "README.md",
    "QUICKSTART.md",
    "SECURITY.md",
    "LICENSE.md",
    "TODO.md",
    "DEVELOPER_QUICKSTART.md",
    "START_HERE.md",
}

BACKUP_GLOBS = ("*~HEAD", "*.orig", "*.rej", "*.bak")

STALE_ROOT_FILES = {
    "test-ci-fix.js",
    "test-server.js",
}

STALE_DUPLICATE_FILES = {
    Path("tests/mock_server_refactored.py"),
}

SUSPICIOUS_NESTED_DIRS = (
    Path(".github/.github"),
    Path("docs/docs"),
    Path("src/src"),
    Path("tests/tests"),
)

BISH_FILENAMES = (".bish-index", ".bish.sqlite")


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    message: str
    remediation: str


def _rel(project_root: Path, candidate: Path) -> str:
    return str(candidate.resolve().relative_to(project_root.resolve()))


def find_root_markdown_issues(project_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    docs_dir = project_root / "docs"

    for md_file in sorted(project_root.glob("*.md"), key=lambda p: p.name.lower()):
        if md_file.name in ALLOWED_ROOT_MARKDOWN:
            continue

        doc_matches = sorted(docs_dir.rglob(md_file.name)) if docs_dir.exists() else []
        if doc_matches:
            findings.append(
                Finding(
                    kind="root-doc-duplicate",
                    path=_rel(project_root, md_file),
                    message=(
                        f"Root markdown duplicates docs copy: {_rel(project_root, doc_matches[0])}"
                    ),
                    remediation="Keep the categorized docs copy and remove the root duplicate.",
                )
            )
        else:
            findings.append(
                Finding(
                    kind="unexpected-root-markdown",
                    path=_rel(project_root, md_file),
                    message="Root markdown file is outside the approved root doc set.",
                    remediation="Move the file under docs/<category>/ and link it from docs/README.md.",
                )
            )

    return findings


def find_backup_artifacts(project_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for pattern in BACKUP_GLOBS:
        for candidate in sorted(project_root.glob(pattern), key=lambda p: p.name.lower()):
            if not candidate.is_file():
                continue
            findings.append(
                Finding(
                    kind="backup-artifact",
                    path=_rel(project_root, candidate),
                    message="Backup/merge artifact found at repository root.",
                    remediation="Remove the artifact and keep only canonical files.",
                )
            )
    return findings


def find_stale_known_files(project_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for filename in sorted(STALE_ROOT_FILES):
        candidate = project_root / filename
        if candidate.is_file():
            findings.append(
                Finding(
                    kind="stale-root-file",
                    path=_rel(project_root, candidate),
                    message="Stale root helper/debug file is present.",
                    remediation="Delete this file or move it under tests/manual if still needed.",
                )
            )

    for relative_path in sorted(STALE_DUPLICATE_FILES, key=str):
        candidate = project_root / relative_path
        if candidate.is_file():
            findings.append(
                Finding(
                    kind="stale-duplicate-file",
                    path=_rel(project_root, candidate),
                    message="Legacy duplicate file is present.",
                    remediation="Keep a single canonical file and remove this duplicate.",
                )
            )

    return findings


def find_suspicious_nested_dirs(project_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for relative_path in SUSPICIOUS_NESTED_DIRS:
        candidate = project_root / relative_path
        if candidate.is_dir() and any(candidate.iterdir()):
            findings.append(
                Finding(
                    kind="suspicious-nested-dir",
                    path=_rel(project_root, candidate),
                    message="Nested duplicate directory pattern found.",
                    remediation="Flatten structure unless there is a clear component boundary.",
                )
            )
    return findings


def find_bish_artifacts(project_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for marker in BISH_FILENAMES:
        for candidate in project_root.rglob(marker):
            if ".git" in candidate.parts or not candidate.is_file():
                continue
            findings.append(
                Finding(
                    kind="bish-artifact",
                    path=_rel(project_root, candidate),
                    message="Unexpected .bish artifact found in tracked tree.",
                    remediation="Delete the artifact and ensure .gitignore keeps it excluded.",
                )
            )
    return findings


def scan_repo(project_root: Path) -> List[Finding]:
    checks: Iterable[List[Finding]] = (
        find_root_markdown_issues(project_root),
        find_backup_artifacts(project_root),
        find_stale_known_files(project_root),
        find_suspicious_nested_dirs(project_root),
        find_bish_artifacts(project_root),
    )
    findings = [finding for check in checks for finding in check]
    findings.sort(key=lambda f: (f.kind, f.path))
    return findings


def cleanup_backup_artifacts(project_root: Path) -> List[str]:
    removed: List[str] = []
    for pattern in BACKUP_GLOBS:
        for candidate in sorted(project_root.glob(pattern), key=lambda p: p.name.lower()):
            if not candidate.is_file():
                continue
            candidate.unlink()
            removed.append(_rel(project_root, candidate))
    return removed


def _print_human(findings: List[Finding], removed: List[str]) -> None:
    print("=== PF Task: Hygiene ===")
    if removed:
        print("Removed backup artifacts:")
        for path in removed:
            print(f"  - {path}")

    if not findings:
        print("No hygiene findings.")
        return

    print(f"Findings ({len(findings)}):")
    for finding in findings:
        print(f"  - [{finding.kind}] {finding.path}: {finding.message}")
        print(f"    remediation: {finding.remediation}")


def _print_json(findings: List[Finding], removed: List[str]) -> None:
    payload = {
        "removed": removed,
        "total_findings": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Repository hygiene scanner")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if findings exist")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument(
        "--cleanup-backups",
        action="store_true",
        help="Remove root backup artifacts (*~HEAD, *.orig, *.rej, *.bak) before scanning",
    )
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT),
        help="Repository root path (defaults to project root)",
    )

    args = parser.parse_args(argv)
    project_root = Path(args.root).resolve()

    removed: List[str] = []
    if args.cleanup_backups:
        removed = cleanup_backup_artifacts(project_root)

    findings = scan_repo(project_root)

    if args.json:
        _print_json(findings, removed)
    else:
        _print_human(findings, removed)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
