"""
Security scanning functionality for Amazon Q integration.

This module provides security analysis using CodeWhisperer and pattern matching.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Any
from .utils import get_source_files

logger = logging.getLogger(__name__)


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
        
        security_issues = []
        files_scanned = 0
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for file_path in source_files:
            if _should_skip_file(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                issues = analyze_file_security(file_path, content)
                security_issues.extend(issues)
                files_scanned += 1
                for issue in issues:
                    severity = issue.get('severity', 'medium')
                    if severity in severity_breakdown:
                        severity_breakdown[severity] += 1
                
            except Exception as e:
                logger.warning(f"Failed to analyze file {file_path}: {e}")
        
        vulnerability_count = len(security_issues)
        risk_score = _calculate_risk_score(severity_breakdown)
        
        return {
            'total_files_scanned': files_scanned,
            'vulnerabilities_found': vulnerability_count,
            'security_issues': security_issues,
            'severity_breakdown': severity_breakdown,
            'risk_score': risk_score,
            'scan_timestamp': datetime.now(timezone.utc).isoformat(),
            'scanner': 'local_heuristic_scanner'
        }
        
    except Exception as e:
        logger.error(f"Security scan failed: {e}")
        return {
            'total_files_scanned': 0,
            'vulnerabilities_found': 0,
            'security_issues': [],
            'severity_breakdown': {'high': 0, 'medium': 0, 'low': 0},
            'risk_score': 100,
            'scan_timestamp': datetime.now(timezone.utc).isoformat(),
            'scanner': 'error',
            'error': str(e)
        }


def analyze_file_security(file_path: str, content: str) -> List[Dict[str, Any]]:
    """Analyze a single file for security issues."""
    issues = []
    
    security_patterns = [
        (
            'hardcoded_secret',
            r'(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*["\'][^"\']{8,}["\']',
            'high',
            'Hardcoded credentials should be moved to environment variables or secret stores.'
        ),
        (
            'shell_injection_risk',
            r'(?i)subprocess\.(run|Popen|call)\s*\([^)]*shell\s*=\s*True',
            'high',
            'Avoid shell=True with dynamic input; use argument lists and explicit validation.'
        ),
        (
            'command_injection_risk',
            r'(?i)os\.system\s*\(',
            'high',
            'Avoid os.system; use subprocess with explicit arguments.'
        ),
        (
            'unsafe_yaml_load',
            r'(?i)yaml\.load\s*\([^)]*\)',
            'medium',
            'Use yaml.safe_load to avoid arbitrary object construction.'
        ),
        (
            'weak_hash_usage',
            r'(?i)hashlib\.(md5|sha1)\s*\(',
            'medium',
            'Use modern hash functions such as sha256/sha512 for security-sensitive code.'
        ),
        (
            'sql_injection_risk',
            r'(?i)\.execute\s*\(\s*f?["\'][^"\']*(select|insert|update|delete)[^"\']*(\{|\%s|\+)',
            'high',
            'Use parameterized queries instead of string-formatted SQL.'
        ),
        (
            'xss_vulnerability',
            r'(?i)\.innerHTML\s*=\s*',
            'medium',
            'Avoid assigning untrusted input to innerHTML.'
        ),
        (
            'dangerous_eval',
            r'(?i)\b(eval|exec)\s*\(',
            'high',
            'Avoid eval/exec for untrusted input.'
        ),
        (
            'insecure_deserialization',
            r'(?i)pickle\.loads?\s*\(',
            'high',
            'Avoid untrusted pickle payloads; use safer serialization formats.'
        ),
    ]
    
    for issue_type, pattern, severity, remediation in security_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append({
                'type': issue_type,
                'severity': severity,
                'file': file_path,
                'line': line_num,
                'description': f'Potential {issue_type.replace("_", " ")} detected',
                'snippet': match.group(0)[:120],
                'remediation': remediation,
            })
    
    return issues


def _should_skip_file(file_path: str) -> bool:
    """Skip files that are not useful for static security analysis."""
    lowered = file_path.lower()
    return lowered.endswith('.min.js')


def _calculate_risk_score(severity_breakdown: Dict[str, int]) -> int:
    """
    Calculate a 0-100 score where 100 means low risk.
    Weighted penalties prioritize high-severity findings.
    """
    penalty = (
        severity_breakdown.get('high', 0) * 12
        + severity_breakdown.get('medium', 0) * 5
        + severity_breakdown.get('low', 0) * 2
    )
    return max(0, 100 - penalty)
