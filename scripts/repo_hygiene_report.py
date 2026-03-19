#!/usr/bin/env python3
"""
Generate a repository hygiene and progress report.

The report is intended for scheduled automation runs and includes:
- Unfinished markers in code files (TODO/FIXME/STUB/etc.)
- Python function stubs (pass-only or ellipsis-only bodies)
- Cleanup candidates (stale duplicate patterns and loose root tests)
- Recent commit direction inferred from commit messages
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


UNFINISHED_PATTERN = re.compile(r"\b(TODO|FIXME|STUB|TBD|XXX|UNFINISHED)\b", re.IGNORECASE)
CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".sh",
    ".yml",
    ".yaml",
    ".json",
    ".json5",
}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "docs",
    "bak",
    "security-reports",
    "playwright-report",
    "dist",
    "build",
}
COMMIT_STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "with",
    "into",
    "this",
    "that",
    "sync",
    "update",
    "updates",
    "workflows",
    "workflow",
    "auto",
}
THEME_KEYWORDS = {
    "automation": {"workflow", "ci", "actions", "sync", "dispatch", "github", "automation"},
    "testing": {"test", "tests", "playwright", "pytest", "coverage"},
    "security": {"security", "audit", "vulnerability", "scan"},
    "cleanup": {"cleanup", "clean", "refactor", "organize", "remove", "stale"},
    "features": {"add", "implement", "support", "enable", "feature"},
}


@dataclass(frozen=True)
class MarkerMatch:
    path: str
    line: int
    content: str


@dataclass(frozen=True)
class StubFunction:
    path: str
    line: int
    name: str


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in rel_parts)


def iter_code_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if path.suffix.lower() in CODE_SUFFIXES:
            yield path


def find_unfinished_markers(root: Path) -> list[MarkerMatch]:
    matches: list[MarkerMatch] = []
    for path in iter_code_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if UNFINISHED_PATTERN.search(line):
                matches.append(
                    MarkerMatch(
                        path=str(path.relative_to(root)),
                        line=idx,
                        content=line.strip(),
                    )
                )
    return sorted(matches, key=lambda item: (item.path, item.line))


def _is_stub_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if len(node.body) != 1:
        return False
    stmt = node.body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return stmt.value.value is Ellipsis
    return False


def find_python_stub_functions(root: Path) -> list[StubFunction]:
    stubs: list[StubFunction] = []
    for path in root.rglob("*.py"):
        if should_skip(path, root):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        rel_path = str(path.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_stub_body(node):
                stubs.append(StubFunction(path=rel_path, line=node.lineno, name=node.name))
    return sorted(stubs, key=lambda item: (item.path, item.line, item.name))


def find_cleanup_candidates(root: Path) -> list[str]:
    candidates: set[str] = set()

    for path in root.rglob("*_refactored.py"):
        if should_skip(path, root):
            continue
        original = path.with_name(path.name.replace("_refactored.py", ".py"))
        if original.exists():
            candidates.add(
                f"{path.relative_to(root)} (duplicate pattern; base file exists: {original.relative_to(root)})"
            )

    for path in root.glob("test*.py"):
        if path.is_file():
            candidates.add(f"{path.name} (root-level test helper; consider moving under tests/)")

    for path in root.glob("*manual*.py"):
        if path.is_file():
            candidates.add(f"{path.name} (manual helper at repo root; review placement)")

    return sorted(candidates)


def get_recent_commit_messages(root: Path, limit: int) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", f"-n{limit}", "--pretty=format:%s"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def infer_direction(commit_messages: list[str]) -> tuple[str, list[str]]:
    if not commit_messages:
        return ("No commit history available for inference.", [])

    theme_scores = Counter()
    word_counts = Counter()
    for message in commit_messages:
        lowered = message.lower()
        tokens = re.findall(r"[a-z0-9\-]+", lowered)
        for token in tokens:
            if token not in COMMIT_STOPWORDS and len(token) > 2:
                word_counts[token] += 1
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                theme_scores[theme] += 1

    if theme_scores:
        top_theme, top_score = theme_scores.most_common(1)[0]
        theme_summary = f"Recent commits are primarily focused on {top_theme} ({top_score}/{len(commit_messages)} commits)."
    else:
        theme_summary = "Recent commits do not map cleanly to a single theme."

    top_terms = [term for term, _ in word_counts.most_common(8)]
    return (theme_summary, top_terms)


def build_report(
    markers: list[MarkerMatch],
    stubs: list[StubFunction],
    cleanup_candidates: list[str],
    commit_messages: list[str],
    max_items: int,
) -> str:
    direction, top_terms = infer_direction(commit_messages)
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    lines: list[str] = []
    lines.append("# Repository Hygiene Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Unfinished markers in code: {len(markers)}")
    lines.append(f"- Python pass/ellipsis stubs: {len(stubs)}")
    lines.append(f"- Cleanup candidates: {len(cleanup_candidates)}")
    lines.append(f"- Commits analyzed: {len(commit_messages)}")
    lines.append("")
    lines.append("## Project Direction (from recent commits)")
    lines.append("")
    lines.append(f"- {direction}")
    if top_terms:
        lines.append(f"- Recurring terms: {', '.join(top_terms)}")
    lines.append("")

    lines.append("## Unfinished Markers")
    lines.append("")
    if markers:
        for item in markers[:max_items]:
            lines.append(f"- `{item.path}:{item.line}` {item.content}")
        if len(markers) > max_items:
            lines.append(f"- ... and {len(markers) - max_items} more")
    else:
        lines.append("- None found in scanned code files.")
    lines.append("")

    lines.append("## Python Stub Functions")
    lines.append("")
    if stubs:
        for item in stubs[:max_items]:
            lines.append(f"- `{item.path}:{item.line}` function `{item.name}`")
        if len(stubs) > max_items:
            lines.append(f"- ... and {len(stubs) - max_items} more")
    else:
        lines.append("- None found.")
    lines.append("")

    lines.append("## Cleanup Candidates")
    lines.append("")
    if cleanup_candidates:
        for item in cleanup_candidates[:max_items]:
            lines.append(f"- {item}")
        if len(cleanup_candidates) > max_items:
            lines.append(f"- ... and {len(cleanup_candidates) - max_items} more")
    else:
        lines.append("- No obvious candidates detected.")
    lines.append("")

    lines.append("## Suggested Next Step")
    lines.append("")
    if markers or stubs:
        lines.append("- Prioritize replacing unfinished code markers/stubs in active runtime paths.")
    elif "automation" in direction:
        lines.append("- Continue automation consolidation with measurable checks and cleanup enforcement.")
    else:
        lines.append("- Implement one incremental feature aligned with the top recurring commit terms.")

    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repository hygiene report.")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--commits", type=int, default=8, help="Number of recent commits to analyze")
    parser.add_argument("--max-items", type=int, default=20, help="Max items per report section")
    parser.add_argument("--output", default="", help="Optional path to write markdown report")
    parser.add_argument(
        "--fail-on-unfinished",
        action="store_true",
        help="Exit non-zero if unfinished markers or stubs are found",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.repo_root).resolve()

    markers = find_unfinished_markers(root)
    stubs = find_python_stub_functions(root)
    cleanup_candidates = find_cleanup_candidates(root)
    commit_messages = get_recent_commit_messages(root, args.commits)
    report = build_report(markers, stubs, cleanup_candidates, commit_messages, args.max_items)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    else:
        print(report)

    if args.fail_on_unfinished and (markers or stubs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
