#!/usr/bin/env python3
"""
Repository hygiene checks for OpSecChat.

This script is designed for local use and CI enforcement. It reports
unfinished markers in source code and catches stale/stray artifacts that
should not remain tracked in the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List


SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".go", ".java", ".sh"}
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "bak",
}
UNFINISHED_PATTERN = re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b")


@dataclass
class Finding:
    category: str
    path: str
    message: str
    fixable: bool = False
    fixed: bool = False


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def _iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if _should_skip(path.relative_to(root)):
            continue
        if path.suffix in SOURCE_EXTENSIONS:
            yield path


def _safe_unlink(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except OSError:
        return False


def _scan_unfinished_markers(root: Path, findings: List[Finding]) -> None:
    for source_file in _iter_source_files(root):
        rel_path = source_file.relative_to(root)
        with source_file.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if UNFINISHED_PATTERN.search(line):
                    findings.append(
                        Finding(
                            category="unfinished_marker",
                            path=f"{rel_path}:{line_number}",
                            message="Unfinished marker found in source file",
                        )
                    )


def _scan_bish_indexes(root: Path, findings: List[Finding], fix: bool) -> None:
    for path in root.rglob(".bish-index"):
        rel = str(path.relative_to(root))
        finding = Finding(
            category="tracked_artifact",
            path=rel,
            message="Tracked .bish-index artifact should be removed",
            fixable=True,
        )
        if fix and _safe_unlink(path):
            finding.fixed = True
            finding.message = "Removed tracked .bish-index artifact"
        findings.append(finding)


def _scan_nested_github(root: Path, findings: List[Finding], fix: bool) -> None:
    nested = root / ".github" / ".github" / "workflows"
    if not nested.exists():
        return

    for workflow in nested.glob("*.[yY][aA][mM][lL]"):
        rel = str(workflow.relative_to(root))
        text = workflow.read_text(encoding="utf-8", errors="replace")
        finding = Finding(
            category="stale_workflow_placeholder",
            path=rel,
            message="Unexpected nested .github/.github workflow file",
            fixable=True,
        )
        if text.strip().startswith("# Placeholder workflow for") and fix and _safe_unlink(workflow):
            finding.fixed = True
            finding.message = "Removed stale nested placeholder workflow"
        findings.append(finding)


def _scan_refactor_duplicates(root: Path, findings: List[Finding]) -> None:
    for candidate in root.rglob("*_refactored.py"):
        rel_candidate = candidate.relative_to(root)
        if _should_skip(rel_candidate):
            continue
        original = candidate.with_name(candidate.name.replace("_refactored.py", ".py"))
        if original.exists():
            findings.append(
                Finding(
                    category="stale_refactor_duplicate",
                    path=str(rel_candidate),
                    message=f"Refactor duplicate exists alongside {original.relative_to(root)}",
                )
            )


def scan_repository(root: Path, fix: bool = False) -> List[Finding]:
    findings: List[Finding] = []
    _scan_unfinished_markers(root, findings)
    _scan_bish_indexes(root, findings, fix=fix)
    _scan_nested_github(root, findings, fix=fix)
    _scan_refactor_duplicates(root, findings)
    return findings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan (default: current directory)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically remove safe known artifacts",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output findings as JSON",
    )
    return parser.parse_args()


def _print_text_report(findings: List[Finding]) -> None:
    if not findings:
        print("Repository hygiene check passed: no issues found.")
        return

    unresolved = [f for f in findings if not f.fixed]
    fixed = [f for f in findings if f.fixed]

    if fixed:
        print("Applied fixes:")
        for item in fixed:
            print(f"- [{item.category}] {item.path}: {item.message}")

    if unresolved:
        print("Remaining findings:")
        for item in unresolved:
            print(f"- [{item.category}] {item.path}: {item.message}")


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    findings = scan_repository(root, fix=args.fix)

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        _print_text_report(findings)

    unresolved = [item for item in findings if not item.fixed]
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
