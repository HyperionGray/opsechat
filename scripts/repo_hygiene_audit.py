#!/usr/bin/env python3
"""
Repository hygiene audit utility.

This script scans the repository for stale or unfinished artifacts that are
easy to miss in day-to-day development:

- Editor/merge backup files (for example: *~HEAD, *.orig, *.rej)
- Nested ".github/.github" placeholder trees
- Placeholder workflow files
- Missing Python script files referenced by GitHub workflow run commands
- Empty suspicious files (excluding known keep files)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
}

BACKUP_SUFFIXES = ("~HEAD", ".orig", ".rej")
KEEP_FILE_NAMES = {".gitkeep", ".keep"}
OPTIONAL_EMPTY_FILE_NAMES = {".bish-index", "__init__.py"}
SUSPICIOUS_SUFFIXES = {
    ".yml",
    ".yaml",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".md",
    "",
}


@dataclass
class Finding:
    kind: str
    severity: str
    path: str
    details: str


def _iter_files(root: Path) -> Iterable[Path]:
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [d for d in dir_names if d not in SKIP_DIRS]
        base = Path(current_root)
        for name in file_names:
            yield base / name


def _read_text_safely(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


class RepoHygieneAudit:
    WORKFLOW_PYTHON_REGEX = re.compile(
        r"\bpython(?:3)?\s+([A-Za-z0-9_./-]+\.py)\b"
    )

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.findings: List[Finding] = []

    def run(self) -> List[Finding]:
        self._check_backup_files()
        self._check_nested_github_directory()
        self._check_placeholder_workflows()
        self._check_missing_workflow_python_scripts()
        self._check_empty_suspicious_files()
        return self.findings

    def _add(self, *, kind: str, severity: str, path: Path, details: str) -> None:
        rel_path = str(path.resolve().relative_to(self.root))
        self.findings.append(
            Finding(kind=kind, severity=severity, path=rel_path, details=details)
        )

    def _check_backup_files(self) -> None:
        for file_path in _iter_files(self.root):
            if any(file_path.name.endswith(suffix) for suffix in BACKUP_SUFFIXES):
                self._add(
                    kind="backup-file",
                    severity="high",
                    path=file_path,
                    details="Remove editor/merge backup artifacts from the repository.",
                )

    def _check_nested_github_directory(self) -> None:
        nested_dir = self.root / ".github" / ".github"
        if nested_dir.exists() and nested_dir.is_dir():
            self._add(
                kind="nested-github-dir",
                severity="high",
                path=nested_dir,
                details="Nested .github/.github directory is usually accidental.",
            )

    def _check_placeholder_workflows(self) -> None:
        workflows_glob = self.root.glob(".github/**/workflows/*.yml")
        for workflow_path in workflows_glob:
            content = _read_text_safely(workflow_path).strip()
            if content.startswith("# Placeholder workflow for "):
                self._add(
                    kind="placeholder-workflow",
                    severity="high",
                    path=workflow_path,
                    details="Replace placeholder workflow with a real workflow or remove it.",
                )

    def _check_missing_workflow_python_scripts(self) -> None:
        for workflow_path in self.root.glob(".github/workflows/*.yml"):
            content = _read_text_safely(workflow_path)
            for matched in self.WORKFLOW_PYTHON_REGEX.findall(content):
                candidate = (self.root / matched).resolve()
                if not candidate.exists():
                    self.findings.append(
                        Finding(
                            kind="missing-workflow-script",
                            severity="critical",
                            path=str(
                                workflow_path.resolve().relative_to(self.root)
                            ),
                            details=(
                                f"Workflow references missing script: {matched}"
                            ),
                        )
                    )

    def _check_empty_suspicious_files(self) -> None:
        for file_path in _iter_files(self.root):
            if file_path.name in KEEP_FILE_NAMES:
                continue
            if file_path.name in OPTIONAL_EMPTY_FILE_NAMES:
                continue
            if file_path.suffix not in SUSPICIOUS_SUFFIXES:
                continue
            if file_path.stat().st_size != 0:
                continue
            self._add(
                kind="empty-file",
                severity="medium",
                path=file_path,
                details="Empty file looks accidental. Remove it or add content.",
            )


def _group_counts(findings: Sequence[Finding]) -> Dict[str, int]:
    grouped: Dict[str, int] = {}
    for finding in findings:
        grouped[finding.kind] = grouped.get(finding.kind, 0) + 1
    return grouped


def _print_report(findings: Sequence[Finding], root: Path) -> None:
    print(f"Repository hygiene audit root: {root}")
    print(f"Findings: {len(findings)}")
    if not findings:
        print("No hygiene problems found.")
        return

    print("\nCounts by category:")
    for kind, count in sorted(_group_counts(findings).items()):
        print(f"  - {kind}: {count}")

    print("\nDetailed findings:")
    for finding in findings:
        print(
            f"[{finding.severity.upper()}] {finding.kind} | {finding.path} | "
            f"{finding.details}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks.")
    parser.add_argument(
        "--root",
        default=".",
        help="Path to repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON in addition to text output.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with status 1 if any findings are detected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    audit = RepoHygieneAudit(root)
    findings = audit.run()
    _print_report(findings, root)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))

    if findings and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
