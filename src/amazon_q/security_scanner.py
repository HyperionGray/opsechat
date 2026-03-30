"""
Security scanning functionality for Amazon Q integration.

The scanner intentionally uses deterministic local heuristics so it can run in
CI and developer environments without requiring live AWS service calls.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .utils import get_source_files

logger = logging.getLogger(__name__)


SECURITY_RULES = [
    {
        "id": "hardcoded_secret",
        "severity": "high",
        "description": "Potential hardcoded credential",
        "pattern": re.compile(
            r"(?i)\b(password|passwd|api[_-]?key|secret|token)\b\s*[:=]\s*['\"]([^'\"]{6,})['\"]"
        ),
    },
    {
        "id": "sql_injection_fstring",
        "severity": "high",
        "description": "Dynamic SQL execution with f-string",
        "pattern": re.compile(r"(?i)\bexecute\s*\(\s*f['\"]"),
    },
    {
        "id": "sql_injection_concat",
        "severity": "high",
        "description": "Dynamic SQL execution with string concatenation",
        "pattern": re.compile(r"(?i)\bexecute\s*\([^,\n]*\+"),
    },
    {
        "id": "xss_innerhtml",
        "severity": "medium",
        "description": "DOM write via innerHTML",
        "pattern": re.compile(r"(?i)\.innerHTML\s*="),
    },
    {
        "id": "subprocess_shell_true",
        "severity": "high",
        "description": "subprocess call with shell=True",
        "pattern": re.compile(
            r"(?i)\bsubprocess\.(run|Popen|call|check_output|check_call)\s*\([^)]*shell\s*=\s*True"
        ),
    },
    {
        "id": "os_system_usage",
        "severity": "medium",
        "description": "os.system call detected",
        "pattern": re.compile(r"(?i)\bos\.system\s*\("),
    },
    {
        "id": "dangerous_eval",
        "severity": "high",
        "description": "eval call detected",
        "pattern": re.compile(r"(?i)\beval\s*\("),
    },
    {
        "id": "pickle_load",
        "severity": "medium",
        "description": "pickle deserialization detected",
        "pattern": re.compile(r"(?i)\bpickle\.loads?\s*\("),
    },
]


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def perform_security_scan(repo_path: str, codewhisperer_client=None) -> Dict[str, Any]:
    """
    Perform local security scanning.

    Args:
        repo_path: Path to repository
        codewhisperer_client: Optional AWS client (presence is reported only)

    Returns:
        Security scan results
    """
    try:
        source_files = sorted(get_source_files(repo_path))
        scanned_files = 0
        security_issues: List[Dict[str, Any]] = []

        for file_path in source_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                    content = file_handle.read()
                issues = analyze_file_security(file_path, content)
                security_issues.extend(issues)
                scanned_files += 1
            except Exception as exc:
                logger.warning("Failed to analyze file %s: %s", file_path, exc)

        severity_summary = {"high": 0, "medium": 0, "low": 0}
        for issue in security_issues:
            sev = issue.get("severity", "low")
            if sev not in severity_summary:
                severity_summary[sev] = 0
            severity_summary[sev] += 1

        return {
            "total_files_scanned": scanned_files,
            "vulnerabilities_found": len(security_issues),
            "security_issues": security_issues,
            "severity_summary": severity_summary,
            "scan_timestamp": _timestamp_utc(),
            "scanner": "local_static_security_analyzer",
            "codewhisperer_configured": bool(codewhisperer_client),
        }
    except Exception as exc:
        logger.error("Security scan failed: %s", exc)
        return {
            "total_files_scanned": 0,
            "vulnerabilities_found": 0,
            "security_issues": [],
            "severity_summary": {"high": 0, "medium": 0, "low": 0},
            "scan_timestamp": _timestamp_utc(),
            "scanner": "error",
            "error": str(exc),
        }


def analyze_file_security(file_path: str, content: str) -> List[Dict[str, Any]]:
    """Analyze a single file for security issues."""
    issues: List[Dict[str, Any]] = []
    seen_locations = set()

    for rule in SECURITY_RULES:
        for match in rule["pattern"].finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            dedupe_key = (rule["id"], line_num, match.group(0))
            if dedupe_key in seen_locations:
                continue
            seen_locations.add(dedupe_key)

            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            issues.append(
                {
                    "type": rule["id"],
                    "severity": rule["severity"],
                    "file": file_path,
                    "line": line_num,
                    "description": rule["description"],
                    "snippet": snippet[:180],
                }
            )

    return issues
