"""
Code quality analysis functionality for Amazon Q integration.

This module computes deterministic quality metrics using local static analysis.
"""

import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .utils import get_source_files

logger = logging.getLogger(__name__)

DEFAULT_MAX_FUNCTION_LINES = 50
DEFAULT_MAX_LINE_LENGTH = 120


def analyze_code_quality(repo_path: str, custom_rules: Optional[Dict] = None, bedrock_client=None) -> Dict[str, Any]:
    """
    Analyze code quality using local deterministic heuristics.

    Args:
        repo_path: Path to repository
        custom_rules: Optional custom quality rule overrides
        bedrock_client: Optional Bedrock client (reserved for future use)

    Returns:
        Code quality analysis results
    """
    try:
        source_files = sorted(get_source_files(repo_path))
        max_files = _resolve_max_files(custom_rules, len(source_files))
        files_to_analyze = source_files[:max_files]

        quality_issues: List[Dict[str, Any]] = []
        summaries: List[Dict[str, Any]] = []

        for file_path in files_to_analyze:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                quality_issues.extend(analyze_file_quality(file_path, content, custom_rules))
                summaries.append(_summarize_file(file_path, content))
            except Exception as e:
                logger.warning(f"Failed to analyze quality for {file_path}: {e}")

        quality_metrics, metrics_details = _calculate_metrics(repo_path, files_to_analyze, quality_issues, summaries)

        return {
            'metrics': quality_metrics,
            'issues': quality_issues,
            'total_files_analyzed': len(files_to_analyze),
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_local_heuristic',
            'metrics_details': metrics_details,
        }

    except Exception as e:
        logger.error(f"Code quality analysis failed: {e}")
        return {
            'metrics': {},
            'issues': [],
            'total_files_analyzed': 0,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'error',
            'error': str(e)
        }


def analyze_file_quality(file_path: str, content: str, custom_rules: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Analyze a single file for code quality issues."""
    issues: List[Dict[str, Any]] = []
    lines = content.split('\n')
    max_function_lines = _rule_int(custom_rules, 'max_function_lines', DEFAULT_MAX_FUNCTION_LINES)
    max_line_length = _rule_int(custom_rules, 'max_line_length', DEFAULT_MAX_LINE_LENGTH)

    function_starts = _find_function_starts(file_path, lines)
    for idx, function_start in enumerate(function_starts):
        function_end = function_starts[idx + 1] if idx + 1 < len(function_starts) else len(lines)
        function_length = function_end - function_start
        if function_length > max_function_lines:
            issues.append({
                'type': 'long_function',
                'severity': 'low',
                'file': file_path,
                'line': function_start + 1,
                'description': f'Function starting at line {function_start + 1} is too long ({function_length} lines)',
                'suggestion': 'Consider breaking this function into smaller units'
            })

    # Check for overly long lines.
    for i, line in enumerate(lines):
        if len(line) > max_line_length:
            issues.append({
                'type': 'long_line',
                'severity': 'low',
                'file': file_path,
                'line': i + 1,
                'description': f'Line exceeds {max_line_length} characters ({len(line)})',
                'suggestion': 'Wrap the line for readability and reviewability'
            })

    # Check for TODO/FIXME markers left in source code.
    for i, line in enumerate(lines):
        if re.search(r'\b(TODO|FIXME|XXX)\b', line):
            issues.append({
                'type': 'unfinished_marker',
                'severity': 'medium',
                'file': file_path,
                'line': i + 1,
                'description': 'Unfinished implementation marker found',
                'suggestion': 'Complete this work or move planning notes to documentation'
            })

    # Check for overly broad exception handlers.
    for i, line in enumerate(lines):
        if re.search(r'^\s*except\s+Exception\b', line):
            issues.append({
                'type': 'broad_exception',
                'severity': 'low',
                'file': file_path,
                'line': i + 1,
                'description': 'Catching broad Exception can hide real failures',
                'suggestion': 'Catch narrower exception types when possible'
            })

    # Check for missing module docstrings in Python files.
    if file_path.endswith('.py'):
        stripped = content.lstrip()
        if not stripped.startswith('"""') and not stripped.startswith("'''"):
            issues.append({
                'type': 'missing_docstring',
                'severity': 'low',
                'file': file_path,
                'line': 1,
                'description': 'Module is missing a docstring',
                'suggestion': 'Add a module-level docstring describing the file purpose'
            })

    return issues


def _resolve_max_files(custom_rules: Optional[Dict], available_count: int) -> int:
    if not custom_rules:
        return available_count
    raw_value = custom_rules.get('max_files')
    if isinstance(raw_value, int) and raw_value > 0:
        return min(raw_value, available_count)
    return available_count


def _rule_int(custom_rules: Optional[Dict], key: str, default: int) -> int:
    if not custom_rules:
        return default
    value = custom_rules.get(key, default)
    if isinstance(value, int) and value > 0:
        return value
    return default


def _find_function_starts(file_path: str, lines: List[str]) -> List[int]:
    starts: List[int] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if file_path.endswith('.py') and (stripped.startswith('def ') or stripped.startswith('async def ')):
            starts.append(idx)
        elif file_path.endswith(('.js', '.ts')):
            if re.search(r'^\s*(async\s+)?function\s+\w+\s*\(', line):
                starts.append(idx)
            elif re.search(r'^\s*(const|let|var)\s+\w+\s*=\s*(async\s*)?\(?.*=>', line):
                starts.append(idx)
    return starts


def _summarize_file(file_path: str, content: str) -> Dict[str, Any]:
    lines = content.split('\n')
    function_starts = _find_function_starts(file_path, lines)
    function_lengths: List[int] = []
    documented_functions = 0

    for idx, function_start in enumerate(function_starts):
        function_end = function_starts[idx + 1] if idx + 1 < len(function_starts) else len(lines)
        function_lengths.append(function_end - function_start)

        if file_path.endswith('.py'):
            cursor = function_start + 1
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            if cursor < len(lines):
                next_line = lines[cursor].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    documented_functions += 1

    comment_lines = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            comment_lines += 1

    stripped_content = content.lstrip()
    has_module_docstring = stripped_content.startswith('"""') or stripped_content.startswith("'''")

    return {
        'file_path': file_path,
        'line_count': len(lines),
        'function_count': len(function_starts),
        'function_lengths': function_lengths,
        'documented_functions': documented_functions,
        'has_module_docstring': has_module_docstring if file_path.endswith('.py') else True,
        'comment_lines': comment_lines,
    }


def _calculate_metrics(
    repo_path: str,
    files_to_analyze: List[str],
    quality_issues: List[Dict[str, Any]],
    summaries: List[Dict[str, Any]],
) -> Any:
    issue_counts = Counter(issue.get('severity', 'low') for issue in quality_issues)
    weighted_issue_count = (
        issue_counts.get('high', 0) * 8 +
        issue_counts.get('medium', 0) * 5 +
        issue_counts.get('low', 0) * 2
    )

    total_lines = sum(summary['line_count'] for summary in summaries)
    total_comment_lines = sum(summary['comment_lines'] for summary in summaries)
    total_functions = sum(summary['function_count'] for summary in summaries)
    all_function_lengths = [
        length
        for summary in summaries
        for length in summary['function_lengths']
    ]
    avg_function_length = (
        sum(all_function_lengths) / len(all_function_lengths)
        if all_function_lengths else 0.0
    )
    long_function_count = sum(1 for length in all_function_lengths if length > DEFAULT_MAX_FUNCTION_LINES)

    py_summaries = [summary for summary in summaries if summary['file_path'].endswith('.py')]
    module_doc_coverage = (
        sum(1 for summary in py_summaries if summary['has_module_docstring']) / len(py_summaries)
        if py_summaries else 1.0
    )
    documented_functions = sum(summary['documented_functions'] for summary in py_summaries)
    total_py_functions = sum(summary['function_count'] for summary in py_summaries)
    function_doc_coverage = (
        documented_functions / total_py_functions
        if total_py_functions else 1.0
    )
    comment_ratio = (total_comment_lines / total_lines) if total_lines else 0.0

    maintainability_score = _clamp_score(
        100 - int(round(weighted_issue_count * 1.5)) - int(round(long_function_count * 1.8))
    )
    complexity_score = _clamp_score(
        100 - int(round(avg_function_length * 1.15)) - int(round(long_function_count * 3.0))
    )
    documentation_score = _clamp_score(int(round(
        module_doc_coverage * 40 +
        function_doc_coverage * 45 +
        min(comment_ratio, 0.15) / 0.15 * 15
    )))

    quality_metrics = {
        'maintainability_score': maintainability_score,
        'complexity_score': complexity_score,
        'documentation_score': documentation_score,
        'test_coverage_estimate': _estimate_test_coverage(repo_path),
    }

    metrics_details = {
        'files_considered': len(files_to_analyze),
        'total_lines_analyzed': total_lines,
        'total_functions': total_functions,
        'average_function_length': round(avg_function_length, 2),
        'long_function_count': long_function_count,
        'issue_counts': dict(issue_counts),
        'module_doc_coverage': round(module_doc_coverage, 3),
        'function_doc_coverage': round(function_doc_coverage, 3),
    }
    return quality_metrics, metrics_details


def _estimate_test_coverage(repo_path: str) -> int:
    source_files = get_source_files(repo_path)
    if not source_files:
        return 0

    test_files = [path for path in source_files if _is_test_file(path)]
    prod_files = [path for path in source_files if not _is_test_file(path)]

    if not prod_files:
        return 100 if test_files else 0

    ratio = len(test_files) / len(prod_files)
    return _clamp_score(int(round(25 + min(ratio, 1.0) * 70)))


def _is_test_file(file_path: str) -> bool:
    path_obj = Path(file_path)
    file_name = path_obj.name.lower()
    parts = [part.lower() for part in path_obj.parts]
    return (
        'tests' in parts or
        file_name.startswith('test_') or
        file_name.endswith('_test.py') or
        '.spec.' in file_name or
        '.test.' in file_name
    )


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))
