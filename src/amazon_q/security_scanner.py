"""
Security scanning functionality for Amazon Q integration.

This module provides security analysis using CodeWhisperer and pattern matching.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)

_SECURITY_PATTERNS = [
    {
        'type': 'hardcoded_secret',
        'pattern': re.compile(
            r'(?i)\b(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?key)\b\s*[:=]\s*["\'][^"\']{6,}["\']'
        ),
        'severity': 'high',
        'description': 'Hardcoded credential-like value detected',
        'confidence': 'high',
    },
    {
        'type': 'sql_injection_fstring',
        'pattern': re.compile(
            r'f["\'][^"\']*(select|insert|update|delete)[^"\']*\{[^}]+\}[^"\']*["\']',
            re.IGNORECASE,
        ),
        'severity': 'high',
        'description': 'SQL query appears to interpolate runtime input',
        'confidence': 'medium',
    },
    {
        'type': 'shell_injection',
        'pattern': re.compile(
            r'subprocess\.(run|Popen|call|check_output|check_call)\([^)]*shell\s*=\s*True',
            re.IGNORECASE,
        ),
        'severity': 'high',
        'description': 'subprocess call with shell=True detected',
        'confidence': 'high',
    },
    {
        'type': 'dynamic_code_execution',
        'pattern': re.compile(r'\b(eval|exec)\s*\('),
        'severity': 'high',
        'description': 'Dynamic code execution primitive detected',
        'confidence': 'medium',
    },
    {
        'type': 'xss_innerhtml',
        'pattern': re.compile(r'innerHTML\s*=\s*[^;]+'),
        'severity': 'medium',
        'description': 'Potential DOM XSS sink via innerHTML assignment',
        'confidence': 'medium',
    },
    {
        'type': 'weak_hash_algorithm',
        'pattern': re.compile(r'hashlib\.(md5|sha1)\s*\(', re.IGNORECASE),
        'severity': 'low',
        'description': 'Weak hash algorithm detected for security-sensitive use',
        'confidence': 'medium',
    },
]


def perform_security_scan(repo_path: str, codewhisperer_client=None) -> Dict[str, Any]:
    """
    Perform security scanning using CodeWhisperer.
    
    Args:
        repo_path: Path to repository
        codewhisperer_client: Optional CodeWhisperer client for AWS integration
        
    Returns:
        Security scan results
    """
    try:
        source_files = [path for path in get_source_files(repo_path) if _is_analyzable_file(path)]

        security_issues: List[Dict[str, Any]] = []
        severity_summary = {'high': 0, 'medium': 0, 'low': 0}
        files_analyzed = 0

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                issues = analyze_file_security(file_path, content)
                security_issues.extend(issues)
                files_analyzed += 1
                for issue in issues:
                    severity = issue.get('severity', 'medium')
                    if severity in severity_summary:
                        severity_summary[severity] += 1

            except Exception as e:
                logger.warning(f"Failed to analyze file {file_path}: {e}")

        vulnerability_count = len(security_issues)
        scanner_name = (
            'codewhisperer_local_fallback' if codewhisperer_client else 'local_pattern_scanner'
        )

        return {
            'total_files_scanned': files_analyzed,
            'vulnerabilities_found': vulnerability_count,
            'severity_summary': severity_summary,
            'risk_score': _calculate_risk_score(severity_summary),
            'security_issues': security_issues,
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': scanner_name
        }

    except Exception as e:
        logger.error(f"Security scan failed: {e}")
        return {
            'total_files_scanned': 0,
            'vulnerabilities_found': 0,
            'severity_summary': {'high': 0, 'medium': 0, 'low': 0},
            'risk_score': 0,
            'security_issues': [],
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': 'error',
            'error': str(e)
        }


def analyze_file_security(file_path: str, content: str) -> List[Dict[str, Any]]:
    """Analyze a single file for security issues."""
    issues: List[Dict[str, Any]] = []
    seen_keys = set()
    lines = content.splitlines()

    for pattern_meta in _SECURITY_PATTERNS:
        matches = pattern_meta['pattern'].finditer(content)
        for match in matches:
            line_num = content.count('\n', 0, match.start()) + 1
            snippet = _extract_line_snippet(lines, line_num, match.group(0))
            issue_key = (pattern_meta['type'], line_num, snippet)
            if issue_key in seen_keys:
                continue
            seen_keys.add(issue_key)
            issues.append({
                'type': pattern_meta['type'],
                'severity': pattern_meta['severity'],
                'file': file_path,
                'line': line_num,
                'description': pattern_meta['description'],
                'snippet': snippet,
                'confidence': pattern_meta['confidence'],
            })

    # Additional focused check: os.system with likely user-controlled input.
    for match in re.finditer(r'os\.system\s*\(([^)]*)\)', content):
        line_num = content.count('\n', 0, match.start()) + 1
        command_expr = match.group(1)
        if re.search(r'(input|user|request|argv|param)', command_expr, re.IGNORECASE):
            snippet = _extract_line_snippet(lines, line_num, match.group(0))
            issue_key = ('command_injection', line_num, snippet)
            if issue_key in seen_keys:
                continue
            seen_keys.add(issue_key)
            issues.append({
                'type': 'command_injection',
                'severity': 'high',
                'file': file_path,
                'line': line_num,
                'description': 'Potential command injection via os.system and user-controlled input',
                'snippet': snippet,
                'confidence': 'medium',
            })

    return issues


def _extract_line_snippet(lines: List[str], line_num: int, fallback: str) -> str:
    """Return a compact line snippet for issue reporting."""
    if 0 < line_num <= len(lines):
        return lines[line_num - 1].strip()[:140]
    return fallback.strip()[:140]


def _calculate_risk_score(severity_summary: Dict[str, int]) -> int:
    """
    Compute a repository-level risk score where higher is better.

    Weights are intentionally conservative to surface high-severity issues quickly.
    """
    high = severity_summary.get('high', 0)
    medium = severity_summary.get('medium', 0)
    low = severity_summary.get('low', 0)
    score = 100 - (high * 20) - (medium * 8) - (low * 3)
    return max(0, min(100, score))


def _is_analyzable_file(file_path: str) -> bool:
    """Skip vendored/minified/generated paths for actionable security results."""
    normalized = file_path.replace('\\', '/').lower()
    file_name = Path(file_path).name.lower()
    excluded_markers = ('/node_modules/', '/bak/', '/dist/', '/build/', '/__pycache__/')
    if any(marker in normalized for marker in excluded_markers):
        return False
    if '.min.' in file_name:
        return False
    return True
