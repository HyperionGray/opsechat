#!/usr/bin/env python3
"""
Repository hygiene checks for scheduled maintenance runs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Sequence

SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".sh"}
MARKER_TOKEN_RE = re.compile(r"\b(?:TODO|FIXME|STUB|TBD|HACK|XXX)\b", re.IGNORECASE)
STALE_SUFFIX_RE = re.compile(r"(~HEAD|\.orig|\.rej|\.bak|\.tmp)$", re.IGNORECASE)
STALE_BASENAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".bish-index",
    ".bish.sqlite",
    "test-ci-fix.js",
    "test-server.js",
}
SKIP_UNFINISHED_MARKER_PREFIXES = ("docs/", "bak/")
SKIP_UNFINISHED_MARKER_SUFFIXES = (".min.js",)


@dataclass(frozen=True)
class HygieneIssue:
    kind: str
    path: str
    message: str
    line: int | None = None


def list_tracked_files(repo_root: Path) -> List[str]:
    """Return tracked file paths relative to repo root."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    entries = result.stdout.decode("utf-8", errors="replace").split("\x00")
    return [entry for entry in entries if entry]


def marker_in_comment(line: str, extension: str) -> bool:
    """Return True when an unfinished marker appears in a line comment."""
    marker_match = MARKER_TOKEN_RE.search(line)
    if not marker_match:
        return False
    marker_index = marker_match.start()

    if extension in {".py", ".sh"}:
        hash_index = line.find("#")
        return hash_index != -1 and hash_index < marker_index

    if extension in {".js", ".ts", ".tsx"}:
        js_comment_starts = [idx for idx in (line.find("//"), line.find("/*")) if idx != -1]
        if not js_comment_starts:
            return False
        return min(js_comment_starts) < marker_index

    return False


def _detect_python_comment_markers(absolute_path: Path, relative_path: str) -> List[HygieneIssue]:
    """Detect unfinished markers in real Python comments only."""
    issues: List[HygieneIssue] = []
    try:
        with absolute_path.open("r", encoding="utf-8", errors="replace") as source:
            for token in tokenize.generate_tokens(source.readline):
                if token.type == tokenize.COMMENT and MARKER_TOKEN_RE.search(token.string):
                    issues.append(
                        HygieneIssue(
                            kind="unfinished_marker",
                            path=relative_path,
                            line=token.start[0],
                            message="unfinished marker found in comment",
                        )
                    )
    except (OSError, tokenize.TokenError):
        return []
    return issues


def detect_unfinished_markers(repo_root: Path, tracked_files: Iterable[str]) -> List[HygieneIssue]:
    """Find unfinished TODO/FIXME style markers in source comments."""
    issues: List[HygieneIssue] = []
    for relative_path in tracked_files:
        if relative_path.startswith(SKIP_UNFINISHED_MARKER_PREFIXES):
            continue
        if relative_path.endswith(SKIP_UNFINISHED_MARKER_SUFFIXES):
            continue

        path_obj = PurePosixPath(relative_path)
        extension = path_obj.suffix
        if extension not in SOURCE_EXTENSIONS:
            continue

        absolute_path = repo_root / relative_path
        if not absolute_path.is_file():
            continue

        if extension == ".py":
            issues.extend(_detect_python_comment_markers(absolute_path, relative_path))
            continue

        try:
            text = absolute_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if marker_in_comment(line, extension):
                issues.append(
                    HygieneIssue(
                        kind="unfinished_marker",
                        path=relative_path,
                        line=line_number,
                        message="unfinished marker found in comment",
                    )
                )
    return issues


def detect_stale_artifacts(repo_root: Path, tracked_files: Iterable[str]) -> List[HygieneIssue]:
    """Find stale backup/debug artifacts that should not be tracked."""
    issues: List[HygieneIssue] = []
    for relative_path in tracked_files:
        if not (repo_root / relative_path).exists():
            continue

        path_obj = PurePosixPath(relative_path)
        basename = path_obj.name

        if basename in STALE_BASENAMES:
            issues.append(
                HygieneIssue(
                    kind="stale_artifact",
                    path=relative_path,
                    message=f"stale artifact tracked: {basename}",
                )
            )
            continue

        if STALE_SUFFIX_RE.search(basename):
            issues.append(
                HygieneIssue(
                    kind="stale_artifact",
                    path=relative_path,
                    message=f"stale backup-like file suffix in {basename}",
                )
            )

    return issues


def detect_redundant_directory_nesting(repo_root: Path, tracked_files: Iterable[str]) -> List[HygieneIssue]:
    """
    Flag paths with immediately repeated directory names.
    Example: src/src/file.py
    """
    issues: List[HygieneIssue] = []
    for relative_path in tracked_files:
        if not (repo_root / relative_path).exists():
            continue

        parts = PurePosixPath(relative_path).parts[:-1]
        for idx in range(len(parts) - 1):
            if parts[idx] == parts[idx + 1]:
                repeated = parts[idx]
                issues.append(
                    HygieneIssue(
                        kind="redundant_nesting",
                        path=relative_path,
                        message=f"repeated nested directory segment: {repeated}/{repeated}",
                    )
                )
                break
    return issues


def run_hygiene_checks(repo_root: Path, tracked_files: Sequence[str]) -> List[HygieneIssue]:
    issues: List[HygieneIssue] = []
    issues.extend(detect_unfinished_markers(repo_root, tracked_files))
    issues.extend(detect_stale_artifacts(repo_root, tracked_files))
    issues.extend(detect_redundant_directory_nesting(repo_root, tracked_files))
    return sorted(issues, key=lambda item: (item.kind, item.path, item.line or 0))


def _print_human(issues: Sequence[HygieneIssue]) -> None:
    if not issues:
        print("[*] Repository hygiene checks passed.")
        return

    print(f"[!] Repository hygiene checks found {len(issues)} issue(s):")
    for issue in issues:
        location = f"{issue.path}:{issue.line}" if issue.line else issue.path
        print(f" - [{issue.kind}] {location} - {issue.message}")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check repository hygiene.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to the git repository root (default: project root).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any issues are found.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()

    try:
        tracked_files = list_tracked_files(repo_root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"[!] Failed to list tracked files: {exc}", file=sys.stderr)
        return 2

    issues = run_hygiene_checks(repo_root, tracked_files)

    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        _print_human(issues)

    if args.strict and issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
