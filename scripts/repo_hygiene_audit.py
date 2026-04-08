#!/usr/bin/env python3
"""
Repository hygiene audit utility.

Scans for:
1. Unfinished markers (TODO/FIXME/STUB/TBD/etc.)
2. Stray files commonly left behind by merges/patches
3. Empty files that are usually accidental
4. Nested duplicate directories (for example .github/.github)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


MARKER_PATTERN = re.compile(
    r"\b(TODO|FIXME|TBD|STUB|XXX|WIP|HACK|UNFINISHED)\b", re.IGNORECASE
)

SOURCE_TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rb",
    ".sh",
    ".bash",
    ".zsh",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".sql",
    ".pf",
}

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "playwright-report",
    "test-results",
    "bak",
}

MARKER_EXCLUDE_FILE_GLOBS = (
    "*.min.js",
    "*.bundle.js",
    "amazon_q_config.yaml",
    "amazon-q-rules.json",
    "scripts/repo_hygiene_audit.py",
)

STRAY_FILE_GLOBS = (
    "*~HEAD",
    "*.orig",
    "*.rej",
    ".DS_Store",
    "Thumbs.db",
)

ALLOWED_EMPTY_FILENAMES = {"__init__.py", ".gitkeep", ".gitignore", ".bish-index"}


@dataclass
class MarkerFinding:
    path: str
    line: int
    marker: str
    snippet: str


@dataclass
class PathFinding:
    path: str
    reason: str


@dataclass
class ScanResult:
    marker_findings: list[MarkerFinding]
    stray_files: list[PathFinding]
    empty_files: list[PathFinding]
    nested_dirs: list[PathFinding]

    @property
    def marker_count(self) -> int:
        return len(self.marker_findings)

    @property
    def stray_file_count(self) -> int:
        return len(self.stray_files)

    @property
    def empty_file_count(self) -> int:
        return len(self.empty_files)

    @property
    def nested_dir_count(self) -> int:
        return len(self.nested_dirs)

    @property
    def total_findings(self) -> int:
        return (
            self.marker_count
            + self.stray_file_count
            + self.empty_file_count
            + self.nested_dir_count
        )


def is_text_candidate(path: Path, scan_docs: bool) -> bool:
    if path.suffix.lower() in SOURCE_TEXT_EXTENSIONS:
        return True
    if scan_docs and path.suffix.lower() in {".md", ".rst", ".txt"}:
        return True
    return path.name in {"Dockerfile", "Makefile", "Pfyfile.pf"}


def iter_repo_files(root: Path) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        current_path = Path(current_root)
        for filename in filenames:
            yield current_path / filename


def iter_repo_dirs(root: Path) -> Iterable[Path]:
    for current_root, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        current_path = Path(current_root)
        yield current_path


def scan_markers(path: Path, relative_path: Path) -> list[MarkerFinding]:
    findings: list[MarkerFinding] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                upper_line = line.upper()
                if "UNFINISHED MARKERS" in upper_line:
                    continue

                matches = list(MARKER_PATTERN.finditer(line))
                unique_markers = {match.group(1).upper() for match in matches}

                # Ignore marker reference lists such as "TODO/FIXME/HACK".
                if len(unique_markers) > 1:
                    continue

                for match in matches:
                    findings.append(
                        MarkerFinding(
                            path=str(relative_path),
                            line=line_number,
                            marker=match.group(1).upper(),
                            snippet=line.strip(),
                        )
                    )
    except OSError:
        return findings
    return findings


def should_scan_markers(path: Path, relative_path: Path, scan_docs: bool) -> bool:
    if not is_text_candidate(path, scan_docs):
        return False

    rel_path_str = str(relative_path)
    if any(fnmatch.fnmatch(rel_path_str, pattern) for pattern in MARKER_EXCLUDE_FILE_GLOBS):
        return False

    if not scan_docs:
        if "docs" in relative_path.parts:
            return False
        if relative_path.name.startswith("TODO"):
            return False
    return True


def scan_repo(root: Path, scan_docs: bool) -> ScanResult:
    marker_findings: list[MarkerFinding] = []
    stray_files: list[PathFinding] = []
    empty_files: list[PathFinding] = []
    nested_dirs: list[PathFinding] = []

    for directory in iter_repo_dirs(root):
        rel_dir = directory.relative_to(root)
        parts = rel_dir.parts
        for idx in range(1, len(parts)):
            if parts[idx] == parts[idx - 1]:
                nested_dirs.append(
                    PathFinding(
                        path=str(rel_dir),
                        reason="Nested duplicate directory names",
                    )
                )
                break

    for file_path in iter_repo_files(root):
        rel_path = file_path.relative_to(root)
        rel_path_str = str(rel_path)

        if any(fnmatch.fnmatch(file_path.name, pattern) for pattern in STRAY_FILE_GLOBS):
            stray_files.append(
                PathFinding(path=rel_path_str, reason="Temporary/backup artifact")
            )

        if rel_path.parts[:2] == (".github", ".github"):
            stray_files.append(
                PathFinding(
                    path=rel_path_str,
                    reason="Nested .github mirror path",
                )
            )

        try:
            file_size = file_path.stat().st_size
        except OSError:
            file_size = -1
        if file_size == 0 and file_path.name not in ALLOWED_EMPTY_FILENAMES:
            empty_files.append(
                PathFinding(path=rel_path_str, reason="Unexpected empty file")
            )

        if should_scan_markers(file_path, rel_path, scan_docs):
            marker_findings.extend(scan_markers(file_path, rel_path))

    return ScanResult(
        marker_findings=marker_findings,
        stray_files=stray_files,
        empty_files=empty_files,
        nested_dirs=nested_dirs,
    )


def build_report(result: ScanResult, root: Path) -> str:
    lines: list[str] = []
    lines.append("# Repository Hygiene Audit Report")
    lines.append("")
    lines.append(f"Root: `{root}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Unfinished markers: {result.marker_count}")
    lines.append(f"- Stray files: {result.stray_file_count}")
    lines.append(f"- Empty files: {result.empty_file_count}")
    lines.append(f"- Nested duplicate directories: {result.nested_dir_count}")
    lines.append(f"- Total findings: {result.total_findings}")
    lines.append("")

    lines.append("## Unfinished markers")
    lines.append("")
    if not result.marker_findings:
        lines.append("None.")
    else:
        for finding in result.marker_findings[:200]:
            lines.append(
                f"- `{finding.path}:{finding.line}` [{finding.marker}] `{finding.snippet}`"
            )
        if result.marker_count > 200:
            lines.append(f"- ... truncated {result.marker_count - 200} additional findings")
    lines.append("")

    lines.append("## Stray files")
    lines.append("")
    if not result.stray_files:
        lines.append("None.")
    else:
        for finding in result.stray_files:
            lines.append(f"- `{finding.path}` ({finding.reason})")
    lines.append("")

    lines.append("## Empty files")
    lines.append("")
    if not result.empty_files:
        lines.append("None.")
    else:
        for finding in result.empty_files:
            lines.append(f"- `{finding.path}` ({finding.reason})")
    lines.append("")

    lines.append("## Nested duplicate directories")
    lines.append("")
    if not result.nested_dirs:
        lines.append("None.")
    else:
        for finding in result.nested_dirs:
            lines.append(f"- `{finding.path}` ({finding.reason})")
    lines.append("")

    return "\n".join(lines)


def build_summary(result: ScanResult, root: Path) -> dict[str, object]:
    return {
        "root": str(root),
        "marker_count": result.marker_count,
        "stray_file_count": result.stray_file_count,
        "empty_file_count": result.empty_file_count,
        "nested_dir_count": result.nested_dir_count,
        "total_findings": result.total_findings,
        "examples": {
            "marker_findings": [asdict(f) for f in result.marker_findings[:25]],
            "stray_files": [asdict(f) for f in result.stray_files[:25]],
            "empty_files": [asdict(f) for f in result.empty_files[:25]],
            "nested_dirs": [asdict(f) for f in result.nested_dirs[:25]],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit repository hygiene.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan (default: current directory)",
    )
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional path to write markdown report",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional path to write JSON summary",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit non-zero when findings are present",
    )
    parser.add_argument(
        "--scan-docs",
        action="store_true",
        help="Include docs and TODO markdown/text files in marker scan",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    result = scan_repo(root, scan_docs=args.scan_docs)

    report = build_report(result, root)
    print(report)

    summary = build_summary(result, root)
    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report + "\n", encoding="utf-8")
    if args.summary_path:
        summary_path = Path(args.summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.fail_on_findings and result.total_findings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
