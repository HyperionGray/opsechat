"""
Code quality analysis functionality for Amazon Q integration.

The implementation in this module is intentionally deterministic and local so
it can run in CI without requiring external LLM calls.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import get_source_files

logger = logging.getLogger(__name__)


DEFAULT_RULES = {
    "long_function_lines": 60,
    "max_line_length": 120,
    "complexity_threshold": 12,
}
def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _merge_rules(custom_rules: Optional[Dict[str, Any]]) -> Dict[str, int]:
    merged = dict(DEFAULT_RULES)
    if not isinstance(custom_rules, dict):
        return merged

    nested = custom_rules.get("quality", {})
    for key in DEFAULT_RULES:
        if key in custom_rules and isinstance(custom_rules[key], int):
            merged[key] = custom_rules[key]
        if isinstance(nested, dict) and key in nested and isinstance(nested[key], int):
            merged[key] = nested[key]
    return merged


def _is_test_or_fixture_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    name = Path(file_path).name.lower()
    return "/tests/" in normalized or name.startswith("test_") or normalized.endswith(".spec.js")


def analyze_code_quality(
    repo_path: str, custom_rules: Optional[Dict] = None, bedrock_client=None
) -> Dict[str, Any]:
    """
    Analyze code quality using local heuristics.

    Args:
        repo_path: Path to repository
        custom_rules: Optional custom quality thresholds
        bedrock_client: Optional Bedrock client (reported as metadata only)

    Returns:
        Code quality analysis results
    """
    try:
        source_files = sorted(get_source_files(repo_path))
        rules = _merge_rules(custom_rules)

        quality_issues: List[Dict[str, Any]] = []
        analyzed_file_count = 0
        complexity_totals: List[int] = []
        documented_modules = 0
        module_count = 0
        test_like_files = 0

        for file_path in source_files:
            if _is_test_or_fixture_file(file_path):
                test_like_files += 1
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                    content = file_handle.read()

                issues = analyze_file_quality(file_path, content, rules)
                quality_issues.extend(issues)
                analyzed_file_count += 1

                file_complexity = sum(
                    1
                    for token in re.findall(
                        r"\b(if|elif|for|while|except|case|catch|&&|\|\|)\b", content
                    )
                )
                complexity_totals.append(file_complexity)

                if file_path.endswith(".py"):
                    module_count += 1
                    if _python_has_module_docstring(content):
                        documented_modules += 1

            except Exception as exc:
                logger.warning("Failed to analyze quality for %s: %s", file_path, exc)

        severity_summary = {"high": 0, "medium": 0, "low": 0}
        for issue in quality_issues:
            severity = issue.get("severity", "low")
            if severity not in severity_summary:
                severity_summary[severity] = 0
            severity_summary[severity] += 1

        avg_complexity = (
            sum(complexity_totals) / len(complexity_totals) if complexity_totals else 0.0
        )
        docs_ratio = documented_modules / module_count if module_count else 1.0
        source_count = analyzed_file_count
        coverage_ratio = (
            min(1.0, test_like_files / source_count) if source_count else 0.0
        )

        issue_penalty = (
            severity_summary["high"] * 8
            + severity_summary["medium"] * 4
            + severity_summary["low"] * 2
        )

        maintainability_score = _safe_score(100 - issue_penalty - max(0, avg_complexity - 8) * 2.5)
        complexity_score = _safe_score(100 - max(0, avg_complexity - 6) * 6 - severity_summary["high"] * 2)
        documentation_score = _safe_score(docs_ratio * 100)
        test_coverage_estimate = _safe_score(min(100, coverage_ratio * 100))

        quality_metrics = {
            "maintainability_score": maintainability_score,
            "complexity_score": complexity_score,
            "documentation_score": documentation_score,
            "test_coverage_estimate": test_coverage_estimate,
        }

        return {
            "metrics": quality_metrics,
            "issues": quality_issues,
            "severity_summary": severity_summary,
            "total_files_analyzed": analyzed_file_count,
            "test_files_skipped": test_like_files,
            "analysis_timestamp": _timestamp_utc(),
            "analyzer": "local_static_quality_analyzer",
            "bedrock_configured": bool(bedrock_client),
        }
    except Exception as exc:
        logger.error("Code quality analysis failed: %s", exc)
        return {
            "metrics": {},
            "issues": [],
            "severity_summary": {"high": 0, "medium": 0, "low": 0},
            "total_files_analyzed": 0,
            "test_files_skipped": 0,
            "analysis_timestamp": _timestamp_utc(),
            "analyzer": "error",
            "error": str(exc),
        }


def _python_has_module_docstring(content: str) -> bool:
    stripped = content.lstrip()
    return stripped.startswith('"""') or stripped.startswith("'''")


def _find_function_ranges(lines: List[str], file_path: str) -> List[Dict[str, Any]]:
    functions: List[Dict[str, Any]] = []
    if file_path.endswith(".py"):
        pattern = re.compile(r"^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    else:
        pattern = re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")

    start_indexes: List[tuple] = []
    for idx, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        if file_path.endswith(".py"):
            indent = len(match.group(1))
            name = match.group(2)
        else:
            indent = len(line) - len(line.lstrip(" "))
            name = match.group(1)
        start_indexes.append((idx, indent, name))

    for i, (start, indent, name) in enumerate(start_indexes):
        end = len(lines) - 1
        for candidate_start, candidate_indent, _ in start_indexes[i + 1 :]:
            if candidate_indent <= indent:
                end = candidate_start - 1
                break
        functions.append({"name": name, "start": start, "end": end})
    return functions


def analyze_file_quality(
    file_path: str, content: str, custom_rules: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """Analyze a single file for code quality issues."""
    rules = _merge_rules(custom_rules)
    issues: List[Dict[str, Any]] = []
    lines = content.split("\n")

    for function in _find_function_ranges(lines, file_path):
        function_length = function["end"] - function["start"] + 1
        if function_length > rules["long_function_lines"]:
            issues.append(
                {
                    "type": "long_function",
                    "severity": "medium",
                    "file": file_path,
                    "line": function["start"] + 1,
                    "description": (
                        f"Function {function['name']} is long ({function_length} lines)"
                    ),
                    "suggestion": "Break the function into smaller units with clear responsibilities.",
                }
            )

        body = "\n".join(lines[function["start"] : function["end"] + 1])
        branch_count = len(re.findall(r"\b(if|elif|for|while|except|case|catch)\b", body))
        if branch_count > rules["complexity_threshold"]:
            issues.append(
                {
                    "type": "high_branch_complexity",
                    "severity": "medium",
                    "file": file_path,
                    "line": function["start"] + 1,
                    "description": (
                        f"Function {function['name']} has high branching complexity ({branch_count})"
                    ),
                    "suggestion": "Split conditional branches into helper functions.",
                }
            )

    for line_no, line in enumerate(lines, start=1):
        if len(line) > rules["max_line_length"]:
            issues.append(
                {
                    "type": "line_too_long",
                    "severity": "low",
                    "file": file_path,
                    "line": line_no,
                    "description": f"Line exceeds {rules['max_line_length']} characters",
                    "suggestion": "Wrap long expressions for readability.",
                }
            )

        marker_match = re.search(r"\b(TODO|FIXME|XXX|TBD)\b", line)
        if marker_match:
            issues.append(
                {
                    "type": "unfinished_marker",
                    "severity": "low",
                    "file": file_path,
                    "line": line_no,
                    "description": f"Unfinished marker found: {marker_match.group(1)}",
                    "suggestion": "Resolve or remove stale implementation markers.",
                }
            )

        if re.match(r"^\s*except\s*:\s*$", line):
            issues.append(
                {
                    "type": "bare_except",
                    "severity": "medium",
                    "file": file_path,
                    "line": line_no,
                    "description": "Bare except detected",
                    "suggestion": "Catch specific exceptions and handle expected failures explicitly.",
                }
            )

    if file_path.endswith(".py") and not _python_has_module_docstring(content):
        issues.append(
            {
                "type": "missing_docstring",
                "severity": "low",
                "file": file_path,
                "line": 1,
                "description": "Module is missing a top-level docstring",
                "suggestion": "Add a module-level docstring describing file purpose.",
            }
        )

    return issues
