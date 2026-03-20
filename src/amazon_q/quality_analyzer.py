"""
Code quality analysis functionality for Amazon Q integration.

This module provides code quality metrics and issue detection.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


def clamp_score(value: float) -> int:
    """Clamp score values to the 0-100 range."""
    return max(0, min(100, int(round(value))))


def _is_test_file(file_path: str) -> bool:
    """Heuristic test-file detection for basic coverage estimation."""
    normalized = file_path.replace('\\', '/').lower()
    basename = normalized.rsplit('/', 1)[-1]
    return (
        '/tests/' in normalized or
        basename.startswith('test_') or
        basename.endswith('.spec.js')
    )


def calculate_quality_metrics(
    source_files: List[str],
    analyzed_files: List[str],
    quality_issues: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Compute quality metrics from discovered files and detected issues."""
    analyzed_count = max(1, len(analyzed_files))
    python_files_analyzed = sum(1 for file_path in analyzed_files if file_path.endswith('.py'))

    long_function_count = sum(1 for issue in quality_issues if issue.get('type') == 'long_function')
    missing_docstring_count = sum(1 for issue in quality_issues if issue.get('type') == 'missing_docstring')
    issue_density = len(quality_issues) / analyzed_count

    maintainability_score = clamp_score(96 - (issue_density * 30))
    complexity_score = clamp_score(95 - (long_function_count * 12))

    if python_files_analyzed == 0:
        documentation_score = 80
    else:
        missing_doc_ratio = missing_docstring_count / python_files_analyzed
        documentation_score = clamp_score(98 - (missing_doc_ratio * 55))

    total_source_files = len(source_files)
    test_files = sum(1 for file_path in source_files if _is_test_file(file_path))
    non_test_files = max(1, total_source_files - test_files)
    test_ratio = test_files / non_test_files
    test_coverage_estimate = clamp_score(min(95, 30 + (test_ratio * 70)))

    return {
        'maintainability_score': maintainability_score,
        'complexity_score': complexity_score,
        'documentation_score': documentation_score,
        'test_coverage_estimate': test_coverage_estimate,
    }


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
        analyzed_files = source_files[:50]
        
        # Analyze each file for quality issues
        for file_path in analyzed_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                issues = analyze_file_quality(file_path, content, custom_rules)
                quality_issues.extend(issues)
                
            except Exception as e:
                logger.warning(f"Failed to analyze quality for {file_path}: {e}")

        quality_metrics = calculate_quality_metrics(
            source_files=source_files,
            analyzed_files=analyzed_files,
            quality_issues=quality_issues,
        )
        
        return {
            'metrics': quality_metrics,
            'issues': quality_issues,
            'total_files_analyzed': len(analyzed_files),
            'total_files_discovered': len(source_files),
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_simulation'
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
    issues = []
    
    # Simple quality checks based on static heuristics.
    lines = content.split('\n')
    
    # Check for long functions
    in_function = False
    function_start = 0
    function_name = ""
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if (
            stripped_line.startswith('def ') or
            stripped_line.startswith('async def ') or
            stripped_line.startswith('function ')
        ):
            if in_function and i - function_start > 50:
                issues.append({
                    'type': 'long_function',
                    'severity': 'low',
                    'file': file_path,
                    'line': function_start + 1,
                    'description': f'Function {function_name} is too long ({i - function_start} lines)',
                    'suggestion': 'Consider breaking this function into smaller functions'
                })
            in_function = True
            function_start = i
            function_name = stripped_line
    
    if in_function and len(lines) - function_start > 50:
        issues.append({
            'type': 'long_function',
            'severity': 'low',
            'file': file_path,
            'line': function_start + 1,
            'description': f'Function {function_name} is too long ({len(lines) - function_start} lines)',
            'suggestion': 'Consider breaking this function into smaller functions'
        })
    
    # Check for missing docstrings in Python files
    if file_path.endswith('.py'):
        if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
            issues.append({
                'type': 'missing_docstring',
                'severity': 'low',
                'file': file_path,
                'line': 1,
                'description': 'Module is missing a docstring',
                'suggestion': 'Add a module-level docstring to describe the purpose of this file'
            })
    
    return issues
