#!/usr/bin/env python3
"""Generate a repository hygiene report for automation workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".sh",
    ".yml",
    ".yaml",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "docs",
    "bak",
    "static",
    "tests",
}

MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|STUB|TBD|XXX|WIP)\b|NotImplementedError")
MARKER_LITERAL_PATTERN = re.compile(r"""["'](TODO|FIXME|STUB|TBD|XXX|WIP):?["']""")

DEPRECATED_WORKFLOWS = {
    "amazon-q-review.yml",
    "amazon-q-security-scan.yml",
    "auto-amazonq-review.yml",
    "auto-copilot-functionality-docs-review.yml",
    "auto-copilot-org-playwright-loop.yaml",
    "auto-copilot-org-playwright-loopv2.yaml",
    "auto-copilot-org-playwright-loopv2.yml",
    "auto-copilot-playwright-auto-test.yml",
    "auto-copilot-test-review-playwright.yml",
    "auto-gpt5-implementation.yml",
    "auto-label-comment-prs.yml",
    "auto-sec-scan.yml",
    "test.yml",
}


@dataclass(frozen=True)
class MarkerHit:
    path: str
    line_number: int
    marker: str
    line: str


def iter_code_files(repo_root: Path) -> Iterable[Path]:
    for root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        root_path = Path(root)
        for filename in filenames:
            path = root_path / filename
            if path.suffix.lower() in CODE_SUFFIXES:
                yield path


def collect_marker_hits(repo_root: Path) -> list[MarkerHit]:
    hits: list[MarkerHit] = []
    for path in iter_code_files(repo_root):
        relative_path = path.relative_to(repo_root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            match = MARKER_PATTERN.search(line)
            if not match:
                continue
            if MARKER_LITERAL_PATTERN.search(line):
                continue
            if "Detect TODO comments" in line:
                continue
            marker = match.group(1) or "NotImplementedError"
            hits.append(
                MarkerHit(
                    path=relative_path,
                    line_number=line_number,
                    marker=marker,
                    line=line.strip(),
                )
            )
    return hits


def collect_duplicate_workflow_files(repo_root: Path) -> dict[str, list[str]]:
    workflow_dir = repo_root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return {}

    files_by_stem: dict[str, list[str]] = defaultdict(list)
    for path in workflow_dir.iterdir():
        if path.suffix not in {".yml", ".yaml"} or not path.is_file():
            continue
        files_by_stem[path.stem].append(path.name)

    return {
        stem: sorted(file_names)
        for stem, file_names in files_by_stem.items()
        if len(file_names) > 1
    }


def collect_deprecated_active_workflows(repo_root: Path) -> list[str]:
    workflow_dir = repo_root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return []
    return sorted(
        workflow_name
        for workflow_name in DEPRECATED_WORKFLOWS
        if (workflow_dir / workflow_name).is_file()
    )


def build_report_data(repo_root: Path) -> dict[str, object]:
    marker_hits = collect_marker_hits(repo_root)
    duplicate_workflows = collect_duplicate_workflow_files(repo_root)
    deprecated_workflows = collect_deprecated_active_workflows(repo_root)

    marker_counts: dict[str, int] = defaultdict(int)
    marker_files: dict[str, int] = defaultdict(int)
    for hit in marker_hits:
        marker_counts[hit.marker] += 1
        marker_files[hit.path] += 1

    top_marker_files = sorted(
        marker_files.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return {
        "summary": {
            "unfinished_marker_count": len(marker_hits),
            "files_with_unfinished_markers": len(marker_files),
            "duplicate_workflow_groups": len(duplicate_workflows),
            "deprecated_active_workflows": len(deprecated_workflows),
        },
        "marker_counts": dict(sorted(marker_counts.items())),
        "top_marker_files": [
            {"path": path, "count": count}
            for path, count in top_marker_files
        ],
        "marker_hits": [asdict(hit) for hit in marker_hits],
        "duplicate_workflows": duplicate_workflows,
        "deprecated_active_workflows": deprecated_workflows,
    }


def to_markdown(report: dict[str, object], max_hits: int) -> str:
    summary = report["summary"]
    marker_counts = report["marker_counts"]
    top_marker_files = report["top_marker_files"]
    marker_hits = report["marker_hits"]
    duplicate_workflows = report["duplicate_workflows"]
    deprecated_workflows = report["deprecated_active_workflows"]

    lines: list[str] = []
    lines.append("## Repository Hygiene Report")
    lines.append("")
    lines.append("### Summary")
    lines.append(
        f"- Unfinished markers in code/workflow files: "
        f"{summary['unfinished_marker_count']}"
    )
    lines.append(
        f"- Files containing unfinished markers: "
        f"{summary['files_with_unfinished_markers']}"
    )
    lines.append(
        f"- Duplicate workflow definition groups (.yml/.yaml): "
        f"{summary['duplicate_workflow_groups']}"
    )
    lines.append(
        f"- Deprecated workflows still active: "
        f"{summary['deprecated_active_workflows']}"
    )
    lines.append("")

    lines.append("### Marker Breakdown")
    if marker_counts:
        for marker, count in marker_counts.items():
            lines.append(f"- {marker}: {count}")
    else:
        lines.append("- None found")
    lines.append("")

    lines.append("### Files With Most Markers")
    if top_marker_files:
        for item in top_marker_files[:10]:
            lines.append(f"- `{item['path']}`: {item['count']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("### Sample Marker Hits")
    if marker_hits:
        for hit in marker_hits[:max_hits]:
            lines.append(
                f"- `{hit['path']}:{hit['line_number']}` "
                f"({hit['marker']}): {hit['line']}"
            )
        remaining = len(marker_hits) - min(len(marker_hits), max_hits)
        if remaining > 0:
            lines.append(f"- ... {remaining} more markers not shown")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("### Duplicate Workflows")
    if duplicate_workflows:
        for stem, file_names in duplicate_workflows.items():
            files_formatted = ", ".join(f"`{name}`" for name in file_names)
            lines.append(f"- `{stem}`: {files_formatted}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("### Deprecated Workflows Still Active")
    if deprecated_workflows:
        for workflow_name in deprecated_workflows:
            lines.append(f"- `{workflow_name}`")
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Path to the repository root (default: current directory).",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--max-hits",
        type=int,
        default=25,
        help="Maximum marker hits to include in markdown output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to write report output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_data = build_report_data(repo_root)

    if args.format == "json":
        rendered = json.dumps(report_data, indent=2, sort_keys=True) + "\n"
    else:
        rendered = to_markdown(report_data, max_hits=args.max_hits)

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
