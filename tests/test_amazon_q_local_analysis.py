"""
Tests for local deterministic Amazon Q analyzers.
"""

import json

from src.amazon_q.architecture_analyzer import analyze_architecture
from src.amazon_q.quality_analyzer import analyze_code_quality
from src.amazon_q.security_scanner import perform_security_scan


def test_quality_analyzer_computes_metrics_and_issues(tmp_path):
    """Quality analyzer should compute metrics from real file contents."""
    src_dir = tmp_path / "src"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir()
    tests_dir.mkdir()

    (src_dir / "module.py").write_text(
        'print("hello")\n'
        '# TODO: refactor this module\n'
        'def very_long_function():\n'
        '    try:\n'
        '        value = 1\n'
        + "".join("        value += 1\n" for _ in range(60))
        + "        return value\n"
        + "    except Exception:\n"
        + "        return 0\n",
        encoding="utf-8",
    )
    (tests_dir / "test_module.py").write_text(
        '"""test module"""\n\ndef test_smoke():\n    assert True\n',
        encoding="utf-8",
    )

    results = analyze_code_quality(str(tmp_path))

    assert results["analyzer"] == "amazon_q_local_heuristic"
    assert results["total_files_analyzed"] >= 2
    for metric in (
        "maintainability_score",
        "complexity_score",
        "documentation_score",
        "test_coverage_estimate",
    ):
        assert 0 <= results["metrics"][metric] <= 100
    assert "metrics_details" in results

    issue_types = {issue["type"] for issue in results["issues"]}
    assert "unfinished_marker" in issue_types
    assert "long_function" in issue_types
    assert "broad_exception" in issue_types


def test_architecture_analyzer_computes_non_placeholder_score(tmp_path):
    """Architecture analyzer should produce score from repository structure."""
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask>=3.0.0\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "dependencies": {"express": "^4.0.0"},
                "devDependencies": {"jest": "^29.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "factory_module.py").write_text(
        '"""factory"""\n\n'
        "class WidgetFactory:\n"
        "    def create_widget(self):\n"
        "        return {}\n",
        encoding="utf-8",
    )

    results = analyze_architecture(str(tmp_path))

    assert results["analyzer"] == "amazon_q_local_architecture"
    assert 0 <= results["architecture_score"] <= 100
    assert results["structure"]["has_readme"] is True
    assert results["dependencies"]["dependency_count"] >= 2
    assert results["dependencies"]["has_lockfile"] is True
    assert results["patterns"]["design_score"] >= 50


def test_security_scanner_detects_real_patterns(tmp_path):
    """Security scanner should find high-risk patterns and severities."""
    (tmp_path / "insecure.py").write_text(
        "import os\n"
        "import yaml\n"
        'password = "hardcoded_password_123"\n'
        "def run(user_input, payload):\n"
        "    os.system(user_input)\n"
        "    return yaml.load(payload)\n",
        encoding="utf-8",
    )

    results = perform_security_scan(str(tmp_path))

    assert results["scanner"] == "amazon_q_local_security"
    assert results["vulnerabilities_found"] >= 3
    assert results["severity_counts"]["high"] >= 2
