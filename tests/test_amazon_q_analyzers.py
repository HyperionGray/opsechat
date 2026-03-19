"""
Tests for local Amazon Q analyzer heuristics.
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure project root is importable in CI and local runs.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.amazon_q.architecture_analyzer import analyze_design_patterns
from src.amazon_q.quality_analyzer import analyze_code_quality
from src.amazon_q.security_scanner import perform_security_scan
from src.amazon_q.utils import get_source_files


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def test_security_scan_analyzes_all_source_files_not_demo_subset():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for index in range(12):
            _write_file(tmp_path / f"unsafe_{index}.py", f'password = "secret_value_{index}"\n')

        result = perform_security_scan(tmpdir)

        assert result["total_files_scanned"] == 12
        assert result["vulnerabilities_found"] >= 12
        assert result["scanner"] == "local_security_heuristics"


def test_quality_analyzer_uses_dynamic_metrics_and_custom_todo_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        _write_file(
            tmp_path / "app.py",
            "\n".join(
                [
                    "def heavy(x):",
                    "    # TODO: simplify",
                    "    if x > 0:",
                    "        if x > 1:",
                    "            if x > 2:",
                    "                if x > 3:",
                    "                    if x > 4:",
                    "                        return x",
                    "    return 0",
                    "",
                ]
            ),
        )
        _write_file(
            tmp_path / "tests" / "test_app.py",
            "\n".join(
                [
                    '"""Test module."""',
                    "",
                    "def test_placeholder():",
                    "    assert 1 == 1",
                    "",
                ]
            ),
        )

        custom_rules = {
            "review": {"max_files": 100},
            "quality": {"rules": {"max_function_length": 5, "max_complexity": 3}},
            "custom_rules": {"todo_detection": {"enabled": True, "patterns": ["TODO:"]}},
        }

        result = analyze_code_quality(tmpdir, custom_rules=custom_rules)

        assert result["total_files_analyzed"] == 2
        assert any(issue["type"] == "todo_comment" for issue in result["issues"])
        assert result["metrics"]["maintainability_score"] < 100
        assert result["metrics"]["complexity_score"] < 100
        assert result["analyzer"] == "amazon_q_local_heuristics"


def test_architecture_pattern_scan_is_not_limited_to_first_ten_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        for index in range(10):
            _write_file(tmp_path / f"module_{index}.py", "def noop():\n    return 1\n")
        _write_file(
            tmp_path / "z_factory_module.py",
            "\n".join(
                [
                    "class TokenFactory:",
                    "    def create_token(self):",
                    "        return 'value'",
                    "",
                ]
            ),
        )

        result = analyze_design_patterns(tmpdir)
        detected = {entry["pattern"] for entry in result["patterns_detected"]}

        assert "factory" in detected
        assert result["pattern_diversity"] >= 1


def test_get_source_files_excludes_minified_assets():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        _write_file(tmp_path / "src" / "app.js", "function app() { return true; }\n")
        _write_file(tmp_path / "static" / "vendor.min.js", "var x = 1;\n")

        files = get_source_files(tmpdir)
        normalized = [str(Path(path).as_posix()) for path in files]

        assert any(path.endswith("/src/app.js") for path in normalized)
        assert all(not path.endswith("/static/vendor.min.js") for path in normalized)
