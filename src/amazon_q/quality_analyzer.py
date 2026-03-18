"""
Code quality analysis functionality for Amazon Q integration.

This module provides code quality metrics and issue detection.
"""

import ast
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


def analyze_code_quality(repo_path: str, custom_rules: Optional[Dict] = None, bedrock_client=None) -> Dict[str, Any]:
    """
    Analyze code quality using Amazon Q.
    
    Args:
        repo_path: Path to repository
        custom_rules: Custom quality rules
        bedrock_client: Optional Bedrock client for AWS integration
        
    Returns:
        Code quality analysis results
    """
    try:
        source_files = [path for path in get_source_files(repo_path) if _is_analyzable_file(path)]

        quality_issues: List[Dict[str, Any]] = []
        total_lines = 0
        comment_lines = 0
        documented_modules = 0
        function_count = 0
        complexity_sum = 0
        public_function_count = 0
        documented_public_functions = 0
        test_file_count = 0

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                issues = analyze_file_quality(file_path, content, custom_rules)
                quality_issues.extend(issues)

                signals = _extract_quality_signals(file_path, content)
                total_lines += signals['line_count']
                comment_lines += signals['comment_lines']
                documented_modules += 1 if signals['module_documented'] else 0
                function_count += signals['function_count']
                complexity_sum += signals['complexity_sum']
                public_function_count += signals['public_function_count']
                documented_public_functions += signals['documented_public_functions']
                if signals['is_test_file']:
                    test_file_count += 1

            except Exception as e:
                logger.warning(f"Failed to analyze quality for {file_path}: {e}")

        quality_metrics = _calculate_quality_metrics(
            source_files=source_files,
            quality_issues=quality_issues,
            total_lines=total_lines,
            comment_lines=comment_lines,
            documented_modules=documented_modules,
            function_count=function_count,
            complexity_sum=complexity_sum,
            test_file_count=test_file_count,
            public_function_count=public_function_count,
            documented_public_functions=documented_public_functions,
        )

        return {
            'metrics': quality_metrics,
            'issues': quality_issues,
            'total_files_analyzed': len(source_files),
            'summary': {
                'total_issues': len(quality_issues),
                'severity_breakdown': _count_issue_severity(quality_issues),
            },
            'analysis_timestamp': _utc_timestamp(),
            'analyzer': 'local_heuristic_analyzer'
        }

    except Exception as e:
        logger.error(f"Code quality analysis failed: {e}")
        return {
            'metrics': {},
            'issues': [],
            'total_files_analyzed': 0,
            'analysis_timestamp': _utc_timestamp(),
            'analyzer': 'error',
            'error': str(e)
        }


def analyze_file_quality(file_path: str, content: str, custom_rules: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Analyze a single file for code quality issues."""
    issues: List[Dict[str, Any]] = []
    rules = _resolve_quality_rules(custom_rules)
    lines = content.split('\n')

    # File-level checks
    if len(lines) > rules['max_file_lines']:
        issues.append({
            'type': 'large_file',
            'severity': 'medium',
            'file': file_path,
            'line': 1,
            'description': f'File has {len(lines)} lines (threshold {rules["max_file_lines"]})',
            'suggestion': 'Split this file into smaller modules where appropriate',
        })

    long_line_reports = 0
    for i, line in enumerate(lines, start=1):
        if len(line) > rules['max_line_length']:
            issues.append({
                'type': 'long_line',
                'severity': 'low',
                'file': file_path,
                'line': i,
                'description': f'Line exceeds {rules["max_line_length"]} characters',
                'suggestion': 'Wrap long expressions or strings for readability',
            })
            long_line_reports += 1
            if long_line_reports >= rules['max_long_line_reports']:
                break

    todo_markers = ('TODO', 'FIXME', 'XXX', 'HACK')
    for i, line in enumerate(lines, start=1):
        if any(marker in line for marker in todo_markers):
            issues.append({
                'type': 'technical_debt_marker',
                'severity': 'low',
                'file': file_path,
                'line': i,
                'description': 'Outstanding TODO/FIXME style marker found',
                'suggestion': 'Resolve or track this item in a dedicated issue',
            })
            break

    # Language-specific checks
    if file_path.endswith('.py'):
        issues.extend(_analyze_python_quality(file_path, content, rules))
    elif file_path.endswith(('.js', '.ts')):
        issues.extend(_analyze_javascript_quality(file_path, content, rules))

    return issues


def _analyze_python_quality(file_path: str, content: str, rules: Dict[str, int]) -> List[Dict[str, Any]]:
    """Analyze Python-specific quality signals via AST."""
    issues: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        issues.append({
            'type': 'syntax_error',
            'severity': 'high',
            'file': file_path,
            'line': exc.lineno or 1,
            'description': f'Python syntax error: {exc.msg}',
            'suggestion': 'Fix syntax to restore parser compatibility',
        })
        return issues

    if not ast.get_docstring(tree):
        issues.append({
            'type': 'missing_docstring',
            'severity': 'low',
            'file': file_path,
            'line': 1,
            'description': 'Module is missing a top-level docstring',
            'suggestion': 'Add a module-level docstring describing file intent',
        })

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_name = node.name
            function_start = getattr(node, 'lineno', 1)
            function_end = getattr(node, 'end_lineno', function_start)
            function_length = max(1, function_end - function_start + 1)
            complexity = _python_function_complexity(node)

            if function_length > rules['max_function_lines']:
                issues.append({
                    'type': 'long_function',
                    'severity': 'medium',
                    'file': file_path,
                    'line': function_start,
                    'description': f'Function {function_name} is too long ({function_length} lines)',
                    'suggestion': 'Break function into smaller composable helpers',
                })

            if complexity > rules['max_function_complexity']:
                issues.append({
                    'type': 'high_complexity',
                    'severity': 'medium',
                    'file': file_path,
                    'line': function_start,
                    'description': f'Function {function_name} has high branching complexity ({complexity})',
                    'suggestion': 'Reduce nesting or split decision-heavy logic into helper functions',
                })

            if not function_name.startswith('_') and not ast.get_docstring(node):
                issues.append({
                    'type': 'missing_function_docstring',
                    'severity': 'low',
                    'file': file_path,
                    'line': function_start,
                    'description': f'Public function {function_name} is missing a docstring',
                    'suggestion': 'Add a short docstring describing inputs, outputs, and behavior',
                })

    return issues


def _analyze_javascript_quality(file_path: str, content: str, rules: Dict[str, int]) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript quality with lightweight heuristics."""
    issues: List[Dict[str, Any]] = []
    lines = content.splitlines()
    function_spans = _extract_js_function_spans(lines)

    for start_line, end_line in function_spans:
        function_length = max(1, end_line - start_line + 1)
        if function_length > rules['max_function_lines']:
            issues.append({
                'type': 'long_function',
                'severity': 'medium',
                'file': file_path,
                'line': start_line,
                'description': f'JavaScript function block is too long ({function_length} lines)',
                'suggestion': 'Split function into smaller units',
            })

        segment = '\n'.join(lines[start_line - 1:end_line])
        complexity = _estimate_branch_complexity(segment)
        if complexity > rules['max_function_complexity']:
            issues.append({
                'type': 'high_complexity',
                'severity': 'medium',
                'file': file_path,
                'line': start_line,
                'description': f'JavaScript function has high branching complexity ({complexity})',
                'suggestion': 'Reduce branch count or extract helper functions',
            })

    if not _has_js_header_comment(lines):
        issues.append({
            'type': 'missing_file_header',
            'severity': 'low',
            'file': file_path,
            'line': 1,
            'description': 'File is missing a short top-of-file comment',
            'suggestion': 'Add a brief comment describing the module purpose',
        })

    return issues


def _extract_quality_signals(file_path: str, content: str) -> Dict[str, Any]:
    """Extract aggregate quality signals used for metric computation."""
    lines = content.splitlines()
    comment_lines = sum(
        1 for line in lines if line.strip().startswith(('#', '//', '/*', '*'))
    )
    module_documented = False
    function_count = 0
    complexity_sum = 0
    public_function_count = 0
    documented_public_functions = 0

    if file_path.endswith('.py'):
        try:
            tree = ast.parse(content)
            module_documented = bool(ast.get_docstring(tree))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_count += 1
                    complexity_sum += _python_function_complexity(node)
                    if not node.name.startswith('_'):
                        public_function_count += 1
                        if ast.get_docstring(node):
                            documented_public_functions += 1
        except SyntaxError:
            module_documented = False
    elif file_path.endswith(('.js', '.ts')):
        module_documented = _has_js_header_comment(lines)
        for start_line, end_line in _extract_js_function_spans(lines):
            function_count += 1
            segment = '\n'.join(lines[start_line - 1:end_line])
            complexity_sum += _estimate_branch_complexity(segment)

    return {
        'line_count': len(lines),
        'comment_lines': comment_lines,
        'module_documented': module_documented,
        'function_count': function_count,
        'complexity_sum': complexity_sum,
        'public_function_count': public_function_count,
        'documented_public_functions': documented_public_functions,
        'is_test_file': _is_test_file(file_path),
    }


def _calculate_quality_metrics(
    source_files: List[str],
    quality_issues: List[Dict[str, Any]],
    total_lines: int,
    comment_lines: int,
    documented_modules: int,
    function_count: int,
    complexity_sum: int,
    test_file_count: int,
    public_function_count: int,
    documented_public_functions: int,
) -> Dict[str, int]:
    """Compute aggregate quality metrics from discovered issues and signals."""
    issue_penalties = {'high': 6, 'medium': 3, 'low': 1}
    penalty_total = sum(issue_penalties.get(issue.get('severity', 'low'), 1) for issue in quality_issues)
    maintainability_score = max(0, 100 - min(80, penalty_total))

    average_complexity = (complexity_sum / function_count) if function_count else 1.0
    complexity_score = max(0, 100 - int(average_complexity * 7))

    module_doc_ratio = documented_modules / max(1, len(source_files))
    comment_ratio = comment_lines / max(1, total_lines)
    public_doc_ratio = (
        documented_public_functions / max(1, public_function_count)
        if public_function_count
        else module_doc_ratio
    )
    documentation_score = int(
        min(100, (module_doc_ratio * 45) + (public_doc_ratio * 35) + min(20, comment_ratio * 100))
    )

    production_file_count = max(1, len(source_files) - test_file_count)
    coverage_ratio = test_file_count / production_file_count
    test_coverage_estimate = int(min(95, coverage_ratio * 100))

    return {
        'maintainability_score': maintainability_score,
        'complexity_score': complexity_score,
        'documentation_score': documentation_score,
        'test_coverage_estimate': test_coverage_estimate,
    }


def _count_issue_severity(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count quality issues by severity."""
    counts = {'high': 0, 'medium': 0, 'low': 0}
    for issue in issues:
        severity = issue.get('severity', 'low')
        if severity in counts:
            counts[severity] += 1
    return counts


def _resolve_quality_rules(custom_rules: Optional[Dict]) -> Dict[str, int]:
    """Resolve quality thresholds from optional custom rule dict."""
    defaults = {
        'max_function_lines': 60,
        'max_function_complexity': 10,
        'max_line_length': 120,
        'max_file_lines': 800,
        'max_long_line_reports': 5,
    }
    if not isinstance(custom_rules, dict):
        return defaults

    merged = defaults.copy()
    nested_quality = custom_rules.get('quality', {})
    if isinstance(nested_quality, dict):
        for key, value in nested_quality.items():
            if key in merged and isinstance(value, int) and value > 0:
                merged[key] = value

    for key, value in custom_rules.items():
        if key in merged and isinstance(value, int) and value > 0:
            merged[key] = value

    return merged


def _python_function_complexity(node: ast.AST) -> int:
    """Estimate function branching complexity from AST nodes."""
    branching_nodes = (
        ast.If,
        ast.For,
        ast.While,
        ast.Try,
        ast.With,
        ast.BoolOp,
        ast.ExceptHandler,
        ast.IfExp,
        ast.comprehension,
    )
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, branching_nodes):
            complexity += 1
    return complexity


def _extract_js_function_spans(lines: List[str]) -> List[tuple]:
    """Extract JavaScript/TypeScript function block spans as (start_line, end_line)."""
    spans: List[tuple] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        is_function_start = bool(
            re.search(r'\bfunction\b', line) or re.search(r'=>\s*\{', line)
        )
        if not is_function_start:
            index += 1
            continue

        start = index + 1
        brace_balance = line.count('{') - line.count('}')
        end_index = index

        if brace_balance <= 0:
            # Handle declarations where "{" appears on a following line.
            probe = index + 1
            while probe < len(lines):
                brace_balance += lines[probe].count('{') - lines[probe].count('}')
                end_index = probe
                if brace_balance > 0:
                    break
                probe += 1
            if brace_balance <= 0:
                index += 1
                continue

        while end_index + 1 < len(lines) and brace_balance > 0:
            end_index += 1
            brace_balance += lines[end_index].count('{') - lines[end_index].count('}')

        spans.append((start, end_index + 1))
        index = end_index + 1

    return spans


def _estimate_branch_complexity(source_segment: str) -> int:
    """Estimate branching complexity for non-Python code."""
    decision_tokens = re.findall(
        r'\b(if|else\s+if|for|while|switch|case|catch)\b|\?',
        source_segment,
        re.IGNORECASE,
    )
    return 1 + len(decision_tokens)


def _has_js_header_comment(lines: List[str]) -> bool:
    """Check if JS/TS file starts with a comment header."""
    for line in lines[:10]:
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*')
    return False


def _is_test_file(file_path: str) -> bool:
    """Return True when file path indicates test code."""
    normalized = file_path.replace('\\', '/').lower()
    file_name = Path(file_path).name.lower()
    return (
        '/tests/' in normalized
        or file_name.startswith('test_')
        or file_name.endswith('.spec.js')
        or file_name.endswith('.test.js')
    )


def _is_analyzable_file(file_path: str) -> bool:
    """Skip vendored/minified/generated paths for quality analysis."""
    normalized = file_path.replace('\\', '/').lower()
    file_name = Path(file_path).name.lower()
    excluded_markers = ('/node_modules/', '/bak/', '/dist/', '/build/', '/__pycache__/')
    if any(marker in normalized for marker in excluded_markers):
        return False
    if '.min.' in file_name:
        return False
    return True


def _utc_timestamp() -> str:
    """Return an RFC3339-style UTC timestamp with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
