#!/usr/bin/env python3
"""
Repository hygiene checks for CI and local development.

This script checks for:
1) Unfinished markers in code/config files.
2) Placeholder workflow files.
3) Nested duplicate workflow directories.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from pathlib import Path
from typing import Iterable, List

UNFINISHED_MARKER_PATTERN = re.compile(
    r"\b(TODO|FIXME|STUB|TBD|XXX|HACK)\b(?:\s*[:(]|$)",
    re.IGNORECASE,
)

CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".yml",
    ".yaml",
}

IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    ".cursor",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "playwright-report",
    "docs",
    "bak",
}

PLACEHOLDER_PREFIX = "# Placeholder workflow for "


def _extract_comment_text(path: Path, line: str) -> str | None:
    suffix = path.suffix.lower()

    if suffix in {".py", ".sh", ".yml", ".yaml"}:
        if "#" not in line:
            return None
        return line.split("#", 1)[1].strip()

    if suffix in {".js", ".ts", ".tsx", ".jsx"}:
        if "//" in line:
            return line.split("//", 1)[1].strip()
        if "/*" in line:
            return line.split("/*", 1)[1].strip()
        stripped = line.lstrip()
        if stripped.startswith("*"):
            return stripped[1:].strip()
        return None

    return None


def _extract_python_comments(text: str) -> Iterable[tuple[int, str]]:
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comment_text = token.string.lstrip("#").strip()
                yield token.start[0], comment_text
    except tokenize.TokenError:
        return


def _iter_candidate_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue

        if path.suffix.lower() not in CODE_SUFFIXES:
            continue

        if path.name.endswith(".min.js"):
            continue

        yield path


def find_unfinished_markers(root: Path) -> List[str]:
    issues: List[str] = []

    for path in _iter_candidate_files(root):
        rel = path.relative_to(root)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            issues.append(f"{rel}: unable to read file ({exc})")
            continue

        if path.suffix.lower() == ".py":
            text = "\n".join(lines)
            comment_entries = _extract_python_comments(text)
        else:
            comment_entries = (
                (lineno, comment_text)
                for lineno, line in enumerate(lines, start=1)
                for comment_text in [_extract_comment_text(path, line)]
                if comment_text
            )

        for lineno, comment_text in comment_entries:
            match = UNFINISHED_MARKER_PATTERN.search(comment_text)
            if not match:
                continue
            marker = match.group(1).upper()
            issues.append(f"{rel}:{lineno}: unfinished marker '{marker}' found in code/config")

    return issues


def find_placeholder_workflow_files(root: Path) -> List[str]:
    issues: List[str] = []
    workflow_dir = root / ".github" / "workflows"

    if not workflow_dir.exists():
        return issues

    for workflow_file in sorted(workflow_dir.glob("*.yml")):
        try:
            lines = workflow_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            rel = workflow_file.relative_to(root)
            issues.append(f"{rel}: unable to read workflow file ({exc})")
            continue

        first_non_empty = next((line.strip() for line in lines if line.strip()), "")
        if first_non_empty.startswith(PLACEHOLDER_PREFIX):
            rel = workflow_file.relative_to(root)
            issues.append(f"{rel}: placeholder workflow file must be replaced")

    return issues


def find_nested_workflow_directories(root: Path) -> List[str]:
    issues: List[str] = []
    nested_dir = root / ".github" / ".github" / "workflows"

    if not nested_dir.exists():
        return issues

    nested_files = sorted(path for path in nested_dir.glob("*") if path.is_file())
    if nested_files:
        for file_path in nested_files:
            rel = file_path.relative_to(root)
            issues.append(f"{rel}: nested duplicate workflow path is not allowed")
    else:
        rel = nested_dir.relative_to(root)
        issues.append(f"{rel}: nested duplicate workflow directory is not allowed")

    return issues


def run_hygiene_checks(root: Path) -> List[str]:
    issues: List[str] = []
    issues.extend(find_unfinished_markers(root))
    issues.extend(find_placeholder_workflow_files(root))
    issues.extend(find_nested_workflow_directories(root))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan (default: current directory)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues = run_hygiene_checks(root)

    if issues:
        print("Repository hygiene checks failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Repository hygiene checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
