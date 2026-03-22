"""
Code quality analysis functionality for Amazon Q integration.

This module provides code quality metrics and issue detection.
"""

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
        source_files = get_source_files(repo_path)

        quality_issues = []
        total_loc = 0
        total_function_lines = 0
        function_count = 0
        module_docstring_count = 0
        python_file_count = 0
        branching_tokens = 0
        
        for file_path in source_files:
            if _should_skip_file(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                issues = analyze_file_quality(file_path, content, custom_rules)
                quality_issues.extend(issues)

                file_loc = sum(1 for line in content.split('\n') if line.strip())
                total_loc += file_loc
                file_function_lines, file_function_count = _measure_function_lengths(content)
                total_function_lines += file_function_lines
                function_count += file_function_count
                branching_tokens += _count_branching_tokens(content)

                if file_path.endswith('.py'):
                    python_file_count += 1
                    if _has_module_docstring(content):
                        module_docstring_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to analyze quality for {file_path}: {e}")

        avg_function_length = (
            round(total_function_lines / function_count, 2) if function_count else 0.0
        )
        documentation_score = _calculate_documentation_score(
            python_file_count=python_file_count,
            module_docstring_count=module_docstring_count,
            total_loc=total_loc,
            source_files=source_files,
        )
        complexity_score = _calculate_complexity_score(
            total_loc=total_loc,
            branching_tokens=branching_tokens,
            avg_function_length=avg_function_length,
            quality_issues=quality_issues,
        )
        maintainability_score = _calculate_maintainability_score(
            quality_issues=quality_issues,
            complexity_score=complexity_score,
            documentation_score=documentation_score,
        )
        test_coverage_estimate = _estimate_test_coverage(repo_path, source_files)

        quality_metrics = {
            'maintainability_score': maintainability_score,
            'complexity_score': complexity_score,
            'documentation_score': documentation_score,
            'test_coverage_estimate': test_coverage_estimate,
            'total_loc': total_loc,
            'function_count': function_count,
            'avg_function_length': avg_function_length,
        }
        
        return {
            'metrics': quality_metrics,
            'issues': quality_issues,
            'total_files_analyzed': len(source_files),
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'analyzer': 'local_heuristic_quality'
        }
        
    except Exception as e:
        logger.error(f"Code quality analysis failed: {e}")
        return {
            'metrics': {},
            'issues': [],
            'total_files_analyzed': 0,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
            'analyzer': 'error',
            'error': str(e)
        }


def analyze_file_quality(file_path: str, content: str, custom_rules: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Analyze a single file for code quality issues."""
    issues = []
    max_function_lines = int((custom_rules or {}).get('max_function_lines', 60))
    max_line_length = int((custom_rules or {}).get('max_line_length', 120))
    
    lines = content.split('\n')
    
    # Check for long functions
    in_function = False
    function_start = 0
    function_name = ""
    
    for i, line in enumerate(lines):
        if _looks_like_function_definition(line):
            if in_function and i - function_start > max_function_lines:
                issues.append({
                    'type': 'long_function',
                    'severity': 'medium',
                    'file': file_path,
                    'line': function_start + 1,
                    'description': f'Function {function_name} is too long ({i - function_start} lines)',
                    'suggestion': 'Consider breaking this function into smaller functions'
                })
            in_function = True
            function_start = i
            function_name = line.strip()

        if len(line) > max_line_length:
            issues.append({
                'type': 'long_line',
                'severity': 'low',
                'file': file_path,
                'line': i + 1,
                'description': f'Line exceeds {max_line_length} characters',
                'suggestion': 'Wrap long lines to improve readability'
            })

        if re.search(r'(?i)\b(TODO|FIXME|XXX|TBD)\b', line):
            issues.append({
                'type': 'unfinished_marker',
                'severity': 'low',
                'file': file_path,
                'line': i + 1,
                'description': 'Unfinished code marker found',
                'suggestion': 'Resolve TODO/FIXME markers before release'
            })
        
        if re.search(r'^\s*except\s*:\s*$', line):
            issues.append({
                'type': 'bare_except',
                'severity': 'medium',
                'file': file_path,
                'line': i + 1,
                'description': 'Bare except catches all exceptions',
                'suggestion': 'Catch specific exceptions to avoid masking bugs'
            })

    if in_function and len(lines) - function_start > max_function_lines:
        issues.append({
            'type': 'long_function',
            'severity': 'medium',
            'file': file_path,
            'line': function_start + 1,
            'description': f'Function {function_name} is too long ({len(lines) - function_start} lines)',
            'suggestion': 'Consider breaking this function into smaller functions'
        })
    
    # Check for missing docstrings in Python files
    if file_path.endswith('.py'):
        if not _has_module_docstring(content):
            issues.append({
                'type': 'missing_docstring',
                'severity': 'low',
                'file': file_path,
                'line': 1,
                'description': 'Module is missing a docstring',
                'suggestion': 'Add a module-level docstring to describe the purpose of this file'
            })
    
    return issues


def _looks_like_function_definition(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith('def ') or stripped.startswith('async def ') or stripped.startswith('function ')


def _measure_function_lengths(content: str) -> tuple[int, int]:
    lines = content.split('\n')
    starts = [idx for idx, line in enumerate(lines) if _looks_like_function_definition(line)]
    if not starts:
        return 0, 0

    total_lines = 0
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(lines)
        total_lines += max(1, end - start)
    return total_lines, len(starts)


def _count_branching_tokens(content: str) -> int:
    patterns = [r'\bif\b', r'\belif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bcase\b', r'\bswitch\b']
    return sum(len(re.findall(pattern, content)) for pattern in patterns)


def _has_module_docstring(content: str) -> bool:
    stripped = content.lstrip()
    return stripped.startswith('"""') or stripped.startswith("'''")


def _calculate_documentation_score(
    python_file_count: int,
    module_docstring_count: int,
    total_loc: int,
    source_files: List[str],
) -> int:
    if not source_files:
        return 0
    if python_file_count == 0:
        return 80

    docstring_ratio = module_docstring_count / max(1, python_file_count)
    scale_penalty = 0 if total_loc < 2000 else 5
    score = int((docstring_ratio * 100) - scale_penalty)
    return max(0, min(100, score))


def _calculate_complexity_score(
    total_loc: int,
    branching_tokens: int,
    avg_function_length: float,
    quality_issues: List[Dict[str, Any]],
) -> int:
    density = branching_tokens / max(1, total_loc)
    long_function_count = sum(1 for issue in quality_issues if issue.get('type') == 'long_function')
    penalty = (density * 100) + (avg_function_length * 0.7) + (long_function_count * 4)
    score = int(100 - penalty)
    return max(0, min(100, score))


def _calculate_maintainability_score(
    quality_issues: List[Dict[str, Any]],
    complexity_score: int,
    documentation_score: int,
) -> int:
    severity_weights = {'high': 8, 'medium': 4, 'low': 2}
    issue_penalty = sum(severity_weights.get(issue.get('severity', 'low'), 2) for issue in quality_issues)
    blended = int((complexity_score * 0.5) + (documentation_score * 0.3) + 20 - issue_penalty * 0.2)
    return max(0, min(100, blended))


def _estimate_test_coverage(repo_path: str, source_files: List[str]) -> int:
    if not source_files:
        return 0

    source_file_count = sum(1 for file_path in source_files if '/tests/' not in file_path.replace('\\', '/'))
    test_file_count = sum(1 for file_path in source_files if '/tests/' in file_path.replace('\\', '/'))

    tests_dir_exists = Path(repo_path, 'tests').exists()
    if source_file_count == 0:
        return 0

    ratio = test_file_count / source_file_count
    base_score = int(min(95, ratio * 140))
    if tests_dir_exists:
        base_score = min(100, base_score + 5)
    return max(0, base_score)


def _should_skip_file(file_path: str) -> bool:
    return file_path.lower().endswith('.min.js')
