"""
Code quality analysis functionality for Amazon Q integration.

This module provides code quality metrics and issue detection.
"""

import ast
import fnmatch
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


def _extract_quality_config(custom_rules: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize quality configuration from optional custom rule payload."""
    config = {
        'max_function_length': 50,
        'max_file_length': 500,
        'require_docstrings': True,
        'max_complexity': 10,
        'max_files': None,
        'file_extensions': None,
        'exclude_paths': None,
        'todo_detection_enabled': False,
        'todo_patterns': ['TODO:', 'FIXME:', 'HACK:'],
        'debug_detection_enabled': False,
        'debug_patterns': ['print\\s*\\(', 'console\\.log\\s*\\('],
        'debug_exclude_files': ['test_*.py', '*_test.py', '*.test.js'],
    }

    if not isinstance(custom_rules, dict):
        return config

    quality_section = custom_rules.get('quality', {})
    rules_section = quality_section.get('rules', {}) if isinstance(quality_section, dict) else {}
    review_section = custom_rules.get('review', {})
    custom_section = custom_rules.get('custom_rules', {})

    config['max_function_length'] = int(rules_section.get('max_function_length', config['max_function_length']))
    config['max_file_length'] = int(rules_section.get('max_file_length', config['max_file_length']))
    config['require_docstrings'] = bool(rules_section.get('require_docstrings', config['require_docstrings']))
    config['max_complexity'] = int(rules_section.get('max_complexity', config['max_complexity']))

    if isinstance(review_section, dict):
        config['max_files'] = review_section.get('max_files')
        config['file_extensions'] = review_section.get('file_extensions')
        config['exclude_paths'] = review_section.get('exclude_paths')

    todo_detection = custom_section.get('todo_detection', {}) if isinstance(custom_section, dict) else {}
    if isinstance(todo_detection, dict):
        config['todo_detection_enabled'] = bool(todo_detection.get('enabled', False))
        config['todo_patterns'] = todo_detection.get('patterns', config['todo_patterns'])

    debug_detection = custom_section.get('debug_statements', {}) if isinstance(custom_section, dict) else {}
    if isinstance(debug_detection, dict):
        config['debug_detection_enabled'] = bool(debug_detection.get('enabled', False))
        config['debug_patterns'] = debug_detection.get('patterns', config['debug_patterns'])
        config['debug_exclude_files'] = debug_detection.get('exclude_files', config['debug_exclude_files'])

    return config


def _is_test_file(file_path: str) -> bool:
    normalized = file_path.replace('\\', '/').lower()
    name = Path(file_path).name.lower()
    return '/tests/' in normalized or name.startswith('test_') or name.endswith('_test.py') or name.endswith('.test.js')


def _calculate_python_function_complexity(function_node: ast.AST) -> int:
    """A lightweight branch-count approximation of function complexity."""
    branch_nodes = [
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.BoolOp,
        ast.IfExp,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.comprehension,
    ]
    if hasattr(ast, 'Match'):
        branch_nodes.append(ast.Match)

    complexity = 1
    branch_tuple = tuple(branch_nodes)
    for node in ast.walk(function_node):
        if isinstance(node, branch_tuple):
            complexity += 1
    return complexity


def _analyze_python_file(file_path: str, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze Python-specific quality signals using AST."""
    issues: List[Dict[str, Any]] = []

    try:
        parsed = ast.parse(content)
    except SyntaxError as exc:
        issues.append({
            'type': 'syntax_error',
            'severity': 'high',
            'file': file_path,
            'line': exc.lineno or 1,
            'description': f'Unable to parse Python file: {exc.msg}',
            'suggestion': 'Fix syntax errors before running quality analysis'
        })
        return issues

    if config['require_docstrings'] and not ast.get_docstring(parsed):
        issues.append({
            'type': 'missing_module_docstring',
            'severity': 'low',
            'file': file_path,
            'line': 1,
            'description': 'Module is missing a top-level docstring',
            'suggestion': 'Add a module-level docstring describing the module purpose'
        })

    for node in ast.walk(parsed):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        start_line = getattr(node, 'lineno', 1)
        end_line = getattr(node, 'end_lineno', start_line)
        function_length = max(1, end_line - start_line + 1)
        function_name = getattr(node, 'name', '<anonymous>')

        if function_length > config['max_function_length']:
            severity = 'medium' if function_length > config['max_function_length'] * 1.5 else 'low'
            issues.append({
                'type': 'long_function',
                'severity': severity,
                'file': file_path,
                'line': start_line,
                'description': (
                    f'Function "{function_name}" exceeds length limit '
                    f'({function_length} > {config["max_function_length"]})'
                ),
                'suggestion': 'Split function into smaller units with clearer responsibilities'
            })

        if config['require_docstrings'] and not ast.get_docstring(node):
            issues.append({
                'type': 'missing_function_docstring',
                'severity': 'low',
                'file': file_path,
                'line': start_line,
                'description': f'Function "{function_name}" is missing a docstring',
                'suggestion': 'Add a concise docstring describing inputs, outputs, and side effects'
            })

        complexity = _calculate_python_function_complexity(node)
        if complexity > config['max_complexity']:
            issues.append({
                'type': 'high_complexity',
                'severity': 'medium',
                'file': file_path,
                'line': start_line,
                'description': (
                    f'Function "{function_name}" has estimated complexity {complexity} '
                    f'(limit: {config["max_complexity"]})'
                ),
                'suggestion': 'Reduce branching and extract helper functions'
            })

    return issues


def _analyze_generic_file(file_path: str, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze non-Python files with heuristic checks."""
    issues: List[Dict[str, Any]] = []
    lines = content.split('\n')

    max_function_length = config['max_function_length']
    function_start = None
    function_name = ''
    brace_depth = 0

    function_start_pattern = re.compile(
        r'^\s*(function\s+\w+|[\w$]+\s*[:=]\s*function|[\w$]+\s*[:=]\s*\(?.*\)?\s*=>)'
    )

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if function_start is None and function_start_pattern.search(stripped):
            function_start = index
            function_name = stripped[:120]
            brace_depth = stripped.count('{') - stripped.count('}')
            continue

        if function_start is not None:
            brace_depth += stripped.count('{') - stripped.count('}')
            if brace_depth <= 0 and ('}' in stripped or stripped.endswith(';')):
                function_length = index - function_start + 1
                if function_length > max_function_length:
                    issues.append({
                        'type': 'long_function',
                        'severity': 'low',
                        'file': file_path,
                        'line': function_start,
                        'description': (
                            f'Function-like block exceeds length limit '
                            f'({function_length} > {max_function_length})'
                        ),
                        'suggestion': 'Split this block into smaller functions'
                    })
                function_start = None
                function_name = ''
                brace_depth = 0

    if function_start is not None:
        function_length = len(lines) - function_start + 1
        if function_length > max_function_length:
            issues.append({
                'type': 'long_function',
                'severity': 'low',
                'file': file_path,
                'line': function_start,
                'description': (
                    f'Function-like block "{function_name}" exceeds length limit '
                    f'({function_length} > {max_function_length})'
                ),
                'suggestion': 'Split this block into smaller functions'
            })

    complexity_keywords = ('if ', 'for ', 'while ', 'switch', 'catch', '&&', '||')
    complexity_signal = sum(sum(keyword in line for keyword in complexity_keywords) for line in lines)
    if complexity_signal > config['max_complexity'] * 5:
        issues.append({
            'type': 'high_file_complexity',
            'severity': 'low',
            'file': file_path,
            'line': 1,
            'description': f'File has high branching complexity signal ({complexity_signal})',
            'suggestion': 'Refactor dense logic into smaller modules'
        })

    return issues


def _detect_custom_pattern_issues(file_path: str, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect optional TODO/debug patterns configured in custom rules."""
    issues: List[Dict[str, Any]] = []
    lines = content.split('\n')

    if config['todo_detection_enabled']:
        compiled_todo_patterns = []
        for pattern in config['todo_patterns']:
            try:
                compiled_todo_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                compiled_todo_patterns.append(re.compile(re.escape(pattern), re.IGNORECASE))

        for line_num, line in enumerate(lines, start=1):
            if any(regex.search(line) for regex in compiled_todo_patterns):
                issues.append({
                    'type': 'todo_comment',
                    'severity': 'low',
                    'file': file_path,
                    'line': line_num,
                    'description': 'TODO/FIXME comment found in source file',
                    'suggestion': 'Complete or remove TODO comments before release'
                })

    if config['debug_detection_enabled']:
        file_name = Path(file_path).name
        if not any(fnmatch.fnmatch(file_name, pattern) for pattern in config['debug_exclude_files']):
            compiled_debug_patterns = []
            for pattern in config['debug_patterns']:
                try:
                    compiled_debug_patterns.append(re.compile(pattern))
                except re.error:
                    compiled_debug_patterns.append(re.compile(re.escape(pattern)))

            for line_num, line in enumerate(lines, start=1):
                if any(regex.search(line) for regex in compiled_debug_patterns):
                    issues.append({
                        'type': 'debug_statement',
                        'severity': 'low',
                        'file': file_path,
                        'line': line_num,
                        'description': 'Debug statement detected in non-test source file',
                        'suggestion': 'Remove or replace debug statements with structured logging'
                    })

    return issues


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
        config = _extract_quality_config(custom_rules)
        source_files = get_source_files(
            repo_path,
            extensions=config['file_extensions'],
            exclude_paths=config['exclude_paths'],
            max_files=config['max_files'],
        )

        quality_issues: List[Dict[str, Any]] = []
        scanned_files = 0

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                issues = analyze_file_quality(file_path, content, config)
                quality_issues.extend(issues)
                scanned_files += 1
            except Exception as e:
                logger.warning(f"Failed to analyze quality for {file_path}: {e}")

        severity_penalty = {'high': 6, 'medium': 3, 'low': 1}
        total_penalty = sum(severity_penalty.get(issue.get('severity', 'low'), 1) for issue in quality_issues)
        issue_density = len(quality_issues) / max(scanned_files, 1)
        maintainability_score = max(0, min(100, int(100 - (issue_density * 8) - total_penalty // 2)))

        complexity_issues = [
            issue for issue in quality_issues
            if issue.get('type') in {'high_complexity', 'high_file_complexity', 'long_function'}
        ]
        complexity_penalty = len(complexity_issues) * 3
        complexity_score = max(0, min(100, int(100 - complexity_penalty)))

        documentation_issues = [
            issue for issue in quality_issues
            if issue.get('type') in {'missing_module_docstring', 'missing_function_docstring'}
        ]
        documentation_score = max(0, min(100, int(100 - (len(documentation_issues) * 4))))

        test_files = [path for path in source_files if _is_test_file(path)]
        non_test_source_files = [path for path in source_files if not _is_test_file(path)]
        test_coverage_estimate = min(
            100,
            int((len(test_files) / max(len(non_test_source_files), 1)) * 100)
        )

        quality_metrics = {
            'maintainability_score': maintainability_score,
            'complexity_score': complexity_score,
            'documentation_score': documentation_score,
            'test_coverage_estimate': test_coverage_estimate,
        }

        return {
            'metrics': quality_metrics,
            'issues': quality_issues,
            'total_files_analyzed': scanned_files,
            'analysis_timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'amazon_q_local_heuristics'
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
    if isinstance(custom_rules, dict) and 'max_function_length' in custom_rules:
        config = custom_rules
    else:
        config = _extract_quality_config(custom_rules)
    issues: List[Dict[str, Any]] = []
    lines = content.split('\n')

    if len(lines) > config['max_file_length']:
        issues.append({
            'type': 'long_file',
            'severity': 'low',
            'file': file_path,
            'line': 1,
            'description': f'File exceeds recommended length ({len(lines)} > {config["max_file_length"]})',
            'suggestion': 'Split file into smaller modules'
        })

    if file_path.endswith('.py'):
        issues.extend(_analyze_python_file(file_path, content, config))
    else:
        issues.extend(_analyze_generic_file(file_path, content, config))

    issues.extend(_detect_custom_pattern_issues(file_path, content, config))
    return issues
