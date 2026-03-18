#!/usr/bin/env python3
"""
Tests for local Amazon Q analyzer heuristics.

These tests validate that the analyzer modules produce data-driven output
instead of fixed placeholder values.
"""

import json
from pathlib import Path

from src.amazon_q.architecture_analyzer import analyze_architecture
from src.amazon_q.quality_analyzer import analyze_code_quality
from src.amazon_q.security_scanner import perform_security_scan


def test_security_scanner_detects_high_risk_patterns(tmp_path):
    """Security scanner should flag hardcoded secrets and risky execution."""
    insecure_file = tmp_path / "insecure.py"
    insecure_file.write_text(
        """
password = "super-secret-password"

import subprocess
import os

def run(user_cmd):
    subprocess.run(user_cmd, shell=True)
    os.system(user_cmd)
""".strip()
    )

    results = perform_security_scan(str(tmp_path))
    issue_types = {issue["type"] for issue in results["security_issues"]}

    assert results["vulnerabilities_found"] >= 2
    assert "hardcoded_secret" in issue_types
    assert "shell_injection" in issue_types
    assert results["severity_summary"]["high"] >= 1
    assert 0 <= results["risk_score"] <= 100


def test_quality_analyzer_reports_non_placeholder_metrics(tmp_path):
    """Quality analyzer should compute issues and metrics from file content."""
    quality_file = tmp_path / "quality_target.py"
    quality_file.write_text(
        """
def very_long_function(data):
    total = 0
    for item in data:
        if item > 10:
            total += item
        elif item > 8:
            total += item
        elif item > 6:
            total += item
        elif item > 4:
            total += item
        elif item > 2:
            total += item
        elif item > 0:
            total += item
        else:
            total += 0
    return total
""".strip()
    )

    results = analyze_code_quality(
        str(tmp_path),
        custom_rules={
            "max_function_lines": 8,
            "max_function_complexity": 4,
            "max_line_length": 120,
        },
    )
    issue_types = {issue["type"] for issue in results["issues"]}
    metrics = results["metrics"]

    assert "long_function" in issue_types
    assert "high_complexity" in issue_types
    assert "missing_docstring" in issue_types
    assert metrics["maintainability_score"] < 100
    assert 0 <= metrics["complexity_score"] <= 100
    assert results["summary"]["total_issues"] >= 3


def test_architecture_analyzer_returns_scored_analysis(tmp_path):
    """Architecture analyzer should calculate structure/dependency/pattern scores."""
    (tmp_path / "README.md").write_text("# Test Repo")
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\nrequests>=2.0.0\n")
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "test-repo",
                "version": "1.0.0",
                "dependencies": {"express": "^4.0.0"},
                "devDependencies": {"eslint": "^9.0.0"},
            }
        )
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "factory.py").write_text(
        """
class MessageFactory:
    def create_message(self):
        return {}
""".strip()
    )
    (src_dir / "blueprint.py").write_text(
        """
from flask import Blueprint
bp = Blueprint("sample", __name__)
""".strip()
    )

    results = analyze_architecture(str(tmp_path))

    assert 0 <= results["architecture_score"] <= 100
    assert results["structure"]["structure_score"] > 0
    assert results["dependencies"]["dependency_count"] >= 4
    assert results["dependencies"]["dependency_health"]["python"]["unpinned"] >= 1
    assert results["patterns"]["pattern_diversity"] >= 1
