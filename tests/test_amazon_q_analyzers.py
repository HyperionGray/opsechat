"""
Unit tests for local Amazon Q analyzer modules.
"""

from pathlib import Path

from src.amazon_q.architecture_analyzer import analyze_architecture
from src.amazon_q.mock_reviewer import mock_review
from src.amazon_q.quality_analyzer import analyze_code_quality
from src.amazon_q.security_scanner import perform_security_scan


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_security_scanner_detects_high_risk_patterns(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "src" / "vuln.py",
        """
import subprocess

password = "supersecret123"

def risky(user_value):
    query = f"SELECT * FROM users WHERE name = '{user_value}'"
    subprocess.run("echo hi", shell=True)
    return eval(query)
""".strip(),
    )

    result = perform_security_scan(str(repo))

    assert result["total_files_scanned"] >= 1
    assert result["vulnerabilities_found"] >= 3
    assert result["severity_summary"]["high"] >= 2
    issue_types = {issue["type"] for issue in result["security_issues"]}
    assert "hardcoded_secret" in issue_types
    assert "subprocess_shell_true" in issue_types
    assert "dangerous_eval" in issue_types


def test_quality_analyzer_reports_unfinished_markers_and_complexity(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "src" / "quality_sample.py",
        """
def very_long_function():
    value = 0
    for i in range(5):
        if i % 2 == 0:
            value += i
        elif i % 3 == 0:
            value += i * 2
        else:
            value += i * 3
    # TODO: remove temporary logic
    try:
        return value
    except:
        return 0
""".strip(),
    )

    result = analyze_code_quality(
        str(repo),
        custom_rules={
            "long_function_lines": 5,
            "complexity_threshold": 2,
            "max_line_length": 80,
        },
    )

    assert result["total_files_analyzed"] == 1
    metrics = result["metrics"]
    assert set(metrics) == {
        "maintainability_score",
        "complexity_score",
        "documentation_score",
        "test_coverage_estimate",
    }
    issue_types = {issue["type"] for issue in result["issues"]}
    assert "long_function" in issue_types
    assert "high_branch_complexity" in issue_types
    assert "unfinished_marker" in issue_types
    assert "bare_except" in issue_types
    assert "missing_docstring" in issue_types


def test_architecture_analyzer_reports_patterns_and_antipatterns(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "README.md", "# Demo Repo")
    _write(repo / "LICENSE", "MIT")
    _write(repo / "requirements.txt", "flask==3.0.0\n")
    _write(repo / "package.json", '{"dependencies": {"x": "1.0.0"}}')
    _write(
        repo / "src" / "models.py",
        """
from dataclasses import dataclass

@dataclass
class User:
    name: str
""".strip(),
    )
    _write(
        repo / "src" / "path_hack.py",
        """
import sys
sys.path.insert(0, "/tmp")
""".strip(),
    )

    result = analyze_architecture(str(repo))
    assert result["architecture_score"] >= 0
    assert "structure" in result
    assert "dependencies" in result
    assert "patterns" in result
    assert "pattern_types_detected" in result["patterns"]
    assert "dataclass" in result["patterns"]["pattern_types_detected"]
    anti_types = {entry["type"] for entry in result["patterns"]["anti_patterns_detected"]}
    assert "direct_sys_path_mutation" in anti_types


def test_mock_review_uses_real_local_analyzers(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "src" / "security.py",
        """
token = "abc123token"

def run(user_data):
    return eval(user_data)
""".strip(),
    )

    result = mock_review(str(repo))
    assert result["mock_mode"] is True
    assert result["service_used"] == "mock_amazon_q"
    assert result["security_analysis"]["vulnerabilities_found"] >= 1
