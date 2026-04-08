#!/usr/bin/env python3
"""
Repository hygiene scanner for OpSecChat.

This script highlights common repository cleanliness issues:
- stale backup files (for example, files ending with '~HEAD')
- misplaced GitHub workflow files under nested '.github/.github/workflows'
- placeholder workflow stubs
- suspicious zero-byte files (excluding known placeholders)
- unfinished markers in production code (TODO/STUB/FIXME/XXX/TBD/UNFINISHED)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


UNFINISHED_RE = re.compile(r"\b(TODO|STUB|FIXME|XXX|TBD|UNFINISHED)\b")
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".go", ".rs", ".java"}
IGNORED_SEGMENTS = {".git", ".venv", "node_modules", "docs", "tests", "bak"}
KNOWN_ZERO_BYTE_FILES = {".gitkeep", ".keep", ".empty", ".bish-index", "__init__.py"}
BACKUP_SUFFIXES = ("~HEAD",)
COMMENT_PREFIXES = ("#", "//", "/*", "*", ";", "--")


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    details: str
    severity: str = "warning"
    safe_to_remove: bool = False


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _is_ignored(path: Path) -> bool:
    return any(segment in IGNORED_SEGMENTS for segment in path.parts)


def find_backup_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.endswith(BACKUP_SUFFIXES):
            findings.append(
                Finding(
                    category="backup-file",
                    path=_relative(path, root),
                    details="Backup/merge artifact file should be removed",
                    safe_to_remove=True,
                )
            )
    return findings


def find_nested_workflow_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    nested_dir = root / ".github" / ".github" / "workflows"
    if not nested_dir.exists():
        return findings

    for path in nested_dir.glob("*.yml"):
        findings.append(
            Finding(
                category="nested-workflow",
                path=_relative(path, root),
                details="Workflow file is in nested .github/.github/workflows and is not active",
                safe_to_remove=True,
            )
        )
    for path in nested_dir.glob("*.yaml"):
        findings.append(
            Finding(
                category="nested-workflow",
                path=_relative(path, root),
                details="Workflow file is in nested .github/.github/workflows and is not active",
                safe_to_remove=True,
            )
        )
    return findings


def _iter_active_workflows(root: Path) -> Iterable[Path]:
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.exists():
        return []
    return list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))


def find_placeholder_workflows(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for workflow in _iter_active_workflows(root):
        try:
            content = workflow.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if content.startswith("# Placeholder workflow"):
            findings.append(
                Finding(
                    category="placeholder-workflow",
                    path=_relative(workflow, root),
                    details="Placeholder workflow content should be replaced with a valid workflow or removed",
                    severity="error",
                    safe_to_remove=False,
                )
            )
    return findings


def find_zero_byte_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in KNOWN_ZERO_BYTE_FILES:
            continue
        if path.stat().st_size != 0:
            continue
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        findings.append(
            Finding(
                category="zero-byte-file",
                path=_relative(path, root),
                details="Unexpected zero-byte file; verify whether it is stale",
                safe_to_remove=False,
            )
        )
    return findings


def find_unfinished_markers(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in CODE_SUFFIXES:
            continue
        if _is_ignored(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if not stripped.startswith(COMMENT_PREFIXES):
                continue
            if UNFINISHED_RE.search(line):
                findings.append(
                    Finding(
                        category="unfinished-marker",
                        path=f"{_relative(path, root)}:{line_number}",
                        details=line.strip(),
                        severity="warning",
                    )
                )
    return findings


def scan_repo(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(find_backup_files(root))
    findings.extend(find_nested_workflow_files(root))
    findings.extend(find_placeholder_workflows(root))
    findings.extend(find_zero_byte_files(root))
    findings.extend(find_unfinished_markers(root))
    findings.sort(key=lambda finding: (finding.category, finding.path))
    return findings


def print_text_report(findings: list[Finding], strict: bool) -> None:
    print("Repository hygiene report")
    print("=======================")
    print(f"Findings: {len(findings)}")
    print(f"Strict mode: {'on' if strict else 'off'}")
    if not findings:
        print("No issues found.")
        return

    for finding in findings:
        safe_label = " [safe-to-remove]" if finding.safe_to_remove else ""
        print(
            f"- [{finding.severity}] {finding.category}: {finding.path}{safe_label}\n"
            f"  -> {finding.details}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan repository for hygiene issues")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository root path",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when findings exist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print findings as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    findings = scan_repo(root)

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print_text_report(findings, strict=args.strict)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
