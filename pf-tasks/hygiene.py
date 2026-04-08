#!/usr/bin/env python3
"""
PF Task: repository hygiene audit and optional cleanup.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, List


CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
}

IGNORE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".cache",
    "playwright-report",
    "test-results",
    "bak",
    "docs",
}

# Keep this list tight to avoid noisy false positives from ordinary prose.
UNFINISHED_PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bSTUB\b"),
    re.compile(r"\bHACK\b"),
    re.compile(r"\bXXX\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bWIP\b"),
    re.compile(r"\bNotImplementedError\b"),
]

BACKUP_FILE_PATTERNS = ("*~HEAD", "*.orig", "*.rej", "*.bak")


@dataclass
class Finding:
    category: str
    path: str
    line: int | None
    detail: str


def is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def iter_scan_files(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if is_ignored(path):
            continue
        if path.suffix in CODE_EXTENSIONS:
            yield path


def is_string_literal_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped[0] in {'"', "'"}


def python_comment_text_by_line(content: str) -> dict[int, str]:
    comments: dict[int, str] = {}
    try:
        tokens = tokenize.generate_tokens(StringIO(content).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string.lstrip("#").strip()
    except tokenize.TokenError:
        return comments
    return comments


def scan_unfinished_markers(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in iter_scan_files(repo_root):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        content = raw.splitlines()
        relative = path.relative_to(repo_root).as_posix()
        py_comment_map: dict[int, str] = {}
        if path.suffix == ".py":
            py_comment_map = python_comment_text_by_line(raw)
        for idx, line in enumerate(content, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#!"):
                continue
            if stripped.startswith("raise NotImplementedError"):
                continue
            if is_string_literal_line(line):
                continue
            line_to_scan = line
            if path.suffix == ".py":
                line_to_scan = py_comment_map.get(idx, "")
                if not line_to_scan:
                    continue
            for pattern in UNFINISHED_PATTERNS:
                if pattern.search(line_to_scan):
                    findings.append(
                        Finding(
                            category="unfinished-marker",
                            path=relative,
                            line=idx,
                            detail=stripped[:180],
                        )
                    )
                    break
    return findings


def scan_backup_files(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    matched_paths = set()
    for pattern in BACKUP_FILE_PATTERNS:
        for path in repo_root.rglob(pattern):
            if path.is_file() and not is_ignored(path):
                matched_paths.add(path)

    for path in sorted(matched_paths):
        findings.append(
            Finding(
                category="backup-file",
                path=path.relative_to(repo_root).as_posix(),
                line=None,
                detail="stale backup or conflict artifact",
            )
        )
    return findings


def cleanup_backup_files(repo_root: Path, findings: List[Finding]) -> int:
    removed = 0
    for finding in findings:
        if finding.category != "backup-file":
            continue
        target = repo_root / finding.path
        try:
            target.unlink(missing_ok=True)
            removed += 1
            print(f"[*] Removed {finding.path}")
        except OSError as exc:
            print(f"[!] Failed to remove {finding.path}: {exc}")
    return removed


def print_report(findings: List[Finding]) -> None:
    if not findings:
        print("[✓] No hygiene issues found")
        return

    unfinished = [f for f in findings if f.category == "unfinished-marker"]
    backups = [f for f in findings if f.category == "backup-file"]

    if unfinished:
        print("Unfinished markers:")
        for finding in unfinished:
            print(f"  - {finding.path}:{finding.line}  {finding.detail}")

    if backups:
        print("Backup files:")
        for finding in backups:
            print(f"  - {finding.path}")

    print(f"[!] Total findings: {len(findings)}")


def build_json_payload(repo_root: Path, findings: List[Finding]) -> str:
    unfinished_count = sum(1 for f in findings if f.category == "unfinished-marker")
    backup_count = sum(1 for f in findings if f.category == "backup-file")
    payload = {
        "repo_root": repo_root.as_posix(),
        "counts": {
            "unfinished-markers": unfinished_count,
            "backup-files": backup_count,
            "total": len(findings),
        },
        "findings": [f.__dict__ for f in findings],
    }
    return json.dumps(payload, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit repository hygiene")
    parser.add_argument("--root", default=None, help="Repository root (defaults to project root)")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when findings exist")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--cleanup-backups",
        action="store_true",
        help="Delete stale backup files that are detected",
    )
    args = parser.parse_args()

    script_root = Path(__file__).resolve().parent.parent
    repo_root = Path(args.root).resolve() if args.root else script_root

    unfinished_findings = scan_unfinished_markers(repo_root)
    backup_findings = scan_backup_files(repo_root)
    findings = unfinished_findings + backup_findings

    if args.cleanup_backups and backup_findings:
        removed = cleanup_backup_files(repo_root, backup_findings)
        print(f"[*] Removed {removed} backup files")
        backup_findings = scan_backup_files(repo_root)
        findings = unfinished_findings + backup_findings

    if args.json:
        print(build_json_payload(repo_root, findings))
    else:
        print_report(findings)

    if args.strict and findings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
