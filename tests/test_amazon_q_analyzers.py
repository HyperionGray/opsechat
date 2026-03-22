"""
Tests for local Amazon Q analyzer heuristics.
"""

from pathlib import Path

from src.amazon_q.architecture_analyzer import analyze_architecture
from src.amazon_q.quality_analyzer import analyze_code_quality
from src.amazon_q.security_scanner import perform_security_scan


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_security_scan_detects_high_risk_patterns(tmp_path: Path):
    _write(
        tmp_path / "app.py",
        """
password = "supersecret123"
import subprocess
subprocess.run("echo test", shell=True)
""".strip(),
    )

    results = perform_security_scan(str(tmp_path))

    assert results["scanner"] == "local_heuristic_scanner"
    assert results["total_files_scanned"] >= 1
    assert results["vulnerabilities_found"] >= 2
    assert results["severity_breakdown"]["high"] >= 1
    assert 0 <= results["risk_score"] <= 100


def test_quality_analysis_computes_metrics_and_issues(tmp_path: Path):
    _write(
        tmp_path / "module.py",
        '''
def very_long_function():
    value = 0
    for i in range(80):
        if i % 2 == 0:
            value += i
        else:
            value -= i
    return value
'''.strip(),
    )
    _write(tmp_path / "tests" / "test_module.py", "def test_stub():\n    assert True\n")

    results = analyze_code_quality(str(tmp_path))

    assert results["analyzer"] == "local_heuristic_quality"
    assert results["total_files_analyzed"] >= 1
    metrics = results["metrics"]
    for key in [
        "maintainability_score",
        "complexity_score",
        "documentation_score",
        "test_coverage_estimate",
        "total_loc",
        "function_count",
        "avg_function_length",
    ]:
        assert key in metrics
    assert 0 <= metrics["maintainability_score"] <= 100
    assert any(issue["type"] == "missing_docstring" for issue in results["issues"])


def test_architecture_analysis_computes_composite_score(tmp_path: Path):
    _write(tmp_path / "README.md", "# Sample\n")
    _write(tmp_path / "LICENSE", "MIT\n")
    _write(tmp_path / ".gitignore", "__pycache__/\n")
    _write(tmp_path / "requirements.txt", "requests>=2.0.0\n")
    _write(
        tmp_path / "src" / "service.py",
        """
class EventObserver:
    def notify(self):
        return None


class UserFactory:
    def create_user(self):
        return {}
""".strip(),
    )

    results = analyze_architecture(str(tmp_path))

    assert results["analyzer"] == "local_heuristic_architecture"
    assert 0 <= results["architecture_score"] <= 100
    assert "dependency_health_score" in results["dependencies"]
    assert results["patterns"]["pattern_diversity"] >= 1
