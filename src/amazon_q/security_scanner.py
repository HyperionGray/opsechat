"""
Security scanning functionality for Amazon Q integration.

This module provides security analysis using CodeWhisperer and pattern matching.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


SECURITY_PATTERNS = [
    {
        'type': 'hardcoded_password',
        'severity': 'high',
        'description': 'Potential hardcoded password detected',
        'pattern': r'(?i)\b(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{4,}["\']',
    },
    {
        'type': 'hardcoded_secret',
        'severity': 'high',
        'description': 'Potential hardcoded secret/token detected',
        'pattern': r'(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*["\'][A-Za-z0-9_\-]{8,}["\']',
    },
    {
        'type': 'sql_injection',
        'severity': 'high',
        'description': 'Potential SQL query string interpolation detected',
        'pattern': r'(?i)(execute|query)\s*\(\s*(f["\']|["\'][^"\']*\+)',
    },
    {
        'type': 'command_injection',
        'severity': 'high',
        'description': 'Potential shell command injection path detected',
        'pattern': r'(?i)(os\.system|subprocess\.(run|call|Popen))\s*\(.*shell\s*=\s*True',
    },
    {
        'type': 'unsafe_eval',
        'severity': 'medium',
        'description': 'Dynamic code execution function detected',
        'pattern': r'(?i)\b(eval|exec)\s*\(',
    },
    {
        'type': 'xss_vulnerability',
        'severity': 'medium',
        'description': 'Potential DOM XSS sink detected',
        'pattern': r'(?i)(innerHTML|document\.write)\s*=?.*',
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
        source_files = get_source_files(repo_path)
        
        security_issues: List[Dict[str, Any]] = []
        vulnerability_count = 0
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        files_scanned = 0

        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                issues = analyze_file_security(file_path, content)
                security_issues.extend(issues)
                vulnerability_count += len(issues)
                files_scanned += 1
                for issue in issues:
                    severity = issue.get('severity', 'low')
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
            except Exception as e:
                logger.warning(f"Failed to analyze file {file_path}: {e}")
        
        return {
            'total_files_scanned': files_scanned,
            'vulnerabilities_found': vulnerability_count,
            'security_issues': security_issues,
            'severity_counts': severity_counts,
            'scan_timestamp': datetime.utcnow().isoformat() + 'Z',
            'scanner': 'local_security_heuristics'
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
    seen = set()

    for pattern_config in SECURITY_PATTERNS:
        issue_type = pattern_config['type']
        pattern = pattern_config['pattern']
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issue_key = (issue_type, line_num, match.group(0))
            if issue_key in seen:
                continue
            seen.add(issue_key)
            issues.append({
                'type': issue_type,
                'severity': pattern_config['severity'],
                'file': file_path,
                'line': line_num,
                'description': pattern_config['description'],
                'snippet': match.group(0)[:100]
            })
    
    return issues
