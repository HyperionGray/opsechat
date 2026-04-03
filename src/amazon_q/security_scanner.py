"""
Security scanning functionality for Amazon Q integration.

This module runs deterministic local static checks and can optionally be extended
with cloud-backed findings when AWS services are available.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

from .utils import get_source_files

logger = logging.getLogger(__name__)


def perform_security_scan(repo_path: str, codewhisperer_client=None) -> Dict[str, Any]:
    """
    Perform security scanning using local heuristics.
    
    Args:
        repo_path: Path to repository
        codewhisperer_client: Optional CodeWhisperer client for AWS integration
        
    Returns:
        Security scan results
    """
    try:
        source_files = sorted(get_source_files(repo_path))
        security_issues: List[Dict[str, Any]] = []

        for file_path in source_files:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
                issues = analyze_file_security(file_path, content)
                security_issues.extend(issues)
            except Exception as e:
                logger.warning(f"Failed to analyze file {file_path}: {e}")

        security_issues.sort(key=lambda issue: (issue.get('file', ''), issue.get('line', 0)))
        severity_counts = _count_severities(security_issues)
        vulnerability_count = len(security_issues)

        # Keep API compatibility: indicate whether a cloud scanner was available.
        cloud_assist = codewhisperer_client is not None

        return {
            'total_files_scanned': len(source_files),
            'vulnerabilities_found': vulnerability_count,
            'security_issues': security_issues,
            'severity_counts': severity_counts,
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': 'amazon_q_local_security',
            'cloud_assist_available': cloud_assist,
        }

    except Exception as e:
        logger.error(f"Security scan failed: {e}")
        return {
            'total_files_scanned': 0,
            'vulnerabilities_found': 0,
            'security_issues': [],
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': 'error',
            'error': str(e)
        }


def analyze_file_security(file_path: str, content: str) -> List[Dict[str, Any]]:
    """Analyze a single file for security issues."""
    issues: List[Dict[str, Any]] = []

    security_patterns: List[Tuple[str, str, str]] = [
        ('hardcoded_password', r'(?i)\b(password|passwd|pwd|secret)\b\s*=\s*["\'][^"\']{4,}["\']', 'high'),
        ('hardcoded_api_key', r'(?i)\b(api[_-]?key|token)\b\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']', 'high'),
        ('sql_injection', r'(?i)\.execute\s*\(\s*f?["\'][^"\']*(\{|\%s)', 'high'),
        ('xss_vulnerability', r'(?i)\.innerHTML\s*=\s*.*(user|input|request|params)', 'medium'),
        ('command_injection', r'(?i)\b(os\.system|subprocess\.(run|Popen|call))\s*\(.*(user|input|request)', 'high'),
        ('insecure_random', r'(?i)\brandom\.(random|randint|choice)\s*\(', 'medium'),
        ('weak_hash', r'(?i)\bhashlib\.(md5|sha1)\s*\(', 'medium'),
        ('unsafe_deserialization', r'(?i)\b(yaml\.load|pickle\.loads?)\s*\(', 'high'),
    ]

    for issue_type, pattern, severity in security_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append({
                'type': issue_type,
                'severity': severity,
                'file': file_path,
                'line': line_num,
                'description': f'Potential {issue_type.replace("_", " ")} detected',
                'snippet': match.group(0)[:100]
            })

    return issues


def _count_severities(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {'low': 0, 'medium': 0, 'high': 0}
    for issue in issues:
        severity = issue.get('severity', 'low')
        if severity not in counts:
            counts['low'] += 1
        else:
            counts[severity] += 1
    return counts
