#!/usr/bin/env python3
"""
Release readiness checks for the repository.

This script is intentionally lightweight so it can run in local
development, CI, and PF task flows.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx"}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}
# Detect unfinished markers in source comments, not arbitrary strings.
MARKER_PATTERN = re.compile(
    r"(^|\s)(#|//|/\*+|\*)\s*(TODO|FIXME|STUB|HACK|XXX|TBD)\b"
)
STALE_FILE_PATTERNS = (
    "*~HEAD",
    "*.orig",
    "*.rej",
    "*.bak",
    "*.tmp",
    "*.old",
)
REQUIRED_PATHS = (
    "README.md",
    "QUICKSTART.md",
    "VERSION",
    "requirements.txt",
    "container-compose.yml",
    "containers/Dockerfile",
    "Pfyfile.pf",
)


@dataclass
class Finding:
    category: str
    path: str
    message: str
    line: Optional[int] = None


def _is_excluded(path: Path, repo_root: Path) -> bool:
    try:
        relative_parts = path.relative_to(repo_root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in relative_parts)


def _iter_files(repo_root: Path, extensions: Optional[Set[str]] = None) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        root = Path(current_root)
        for filename in filenames:
            file_path = root / filename
            if extensions and file_path.suffix not in extensions:
                continue
            yield file_path


def scan_required_paths(repo_root: Path, required_paths: Optional[Iterable[str]] = None) -> List[Finding]:
    findings: List[Finding] = []
    required = tuple(required_paths or REQUIRED_PATHS)
    for required_path in required:
        if not (repo_root / required_path).exists():
            findings.append(
                Finding(
                    category="required-path",
                    path=required_path,
                    message="missing required release artifact",
                )
            )
    return findings


def scan_unfinished_markers(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for file_path in _iter_files(repo_root, SOURCE_EXTENSIONS):
        if _is_excluded(file_path, repo_root):
            continue
        relative = str(file_path.relative_to(repo_root))
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, start=1):
                if MARKER_PATTERN.search(line):
                    findings.append(
                        Finding(
                            category="unfinished-marker",
                            path=relative,
                            line=line_number,
                            message="contains release-blocking marker",
                        )
                    )
    return findings


def scan_stale_files(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    seen: Set[Path] = set()
    for pattern in STALE_FILE_PATTERNS:
        for file_path in repo_root.rglob(pattern):
            if file_path in seen:
                continue
            seen.add(file_path)
            if _is_excluded(file_path, repo_root):
                continue
            findings.append(
                Finding(
                    category="stale-file",
                    path=str(file_path.relative_to(repo_root)),
                    message="stale backup/reject file should be removed",
                )
            )
    return findings


def run_checks(repo_root: Path, required_paths: Optional[Iterable[str]] = None) -> List[Finding]:
    findings: List[Finding] = []
    findings.extend(scan_required_paths(repo_root, required_paths=required_paths))
    findings.extend(scan_unfinished_markers(repo_root))
    findings.extend(scan_stale_files(repo_root))
    return findings


def _print_human_report(findings: List[Finding]) -> None:
    if not findings:
        print("[OK] Release readiness checks passed.")
        return

    print("[FAIL] Release readiness checks found issues:")
    by_category: Dict[str, List[Finding]] = {}
    for finding in findings:
        by_category.setdefault(finding.category, []).append(finding)

    for category in sorted(by_category):
        print(f"\n- {category}")
        for finding in by_category[category]:
            location = finding.path
            if finding.line is not None:
                location = f"{location}:{finding.line}"
            print(f"  - {location}: {finding.message}")

    print(f"\nTotal issues: {len(findings)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run release readiness checks")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to repository root",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON findings",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    findings = run_checks(repo_root)

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        _print_human_report(findings)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
