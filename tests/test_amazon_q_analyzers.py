from pathlib import Path

from src.amazon_q.architecture_analyzer import analyze_architecture
from src.amazon_q.quality_analyzer import analyze_code_quality, analyze_file_quality


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_architecture_score_reflects_project_hygiene(tmp_path):
    good_repo = tmp_path / "good_repo"
    weak_repo = tmp_path / "weak_repo"
    good_repo.mkdir()
    weak_repo.mkdir()

    _write_file(good_repo / "README.md", "# Good Repo\n")
    _write_file(good_repo / "LICENSE", "MIT\n")
    _write_file(good_repo / ".gitignore", "__pycache__/\n")
    _write_file(good_repo / "requirements.txt", "flask\nrequests\n")
    _write_file(good_repo / "package-lock.json", "{}\n")
    _write_file(
        good_repo / "src" / "user_factory.py",
        "class UserFactory:\n"
        "    def create_user(self, name):\n"
        "        return {'name': name}\n",
    )

    many_deps = "\n".join(f"package{i}" for i in range(120))
    _write_file(weak_repo / "requirements.txt", many_deps)
    _write_file(weak_repo / "app.py", "print('hello')\n")

    good_result = analyze_architecture(str(good_repo))
    weak_result = analyze_architecture(str(weak_repo))

    assert 0 <= good_result["architecture_score"] <= 100
    assert 0 <= weak_result["architecture_score"] <= 100
    assert good_result["architecture_score"] > weak_result["architecture_score"]
    assert good_result["architecture_score"] != 88


def test_analyze_file_quality_flags_long_function_at_end_of_file():
    body = "\n".join(f"    value += {idx}" for idx in range(60))
    content = f'def giant_function():\n    value = 0\n{body}\n    return value\n'

    issues = analyze_file_quality("module.py", content)
    issue_types = {issue["type"] for issue in issues}

    assert "long_function" in issue_types


def test_quality_metrics_improve_with_better_code_and_tests(tmp_path):
    weak_repo = tmp_path / "weak_quality_repo"
    strong_repo = tmp_path / "strong_quality_repo"
    weak_repo.mkdir()
    strong_repo.mkdir()

    weak_body = "\n".join("    total += 1" for _ in range(55))
    _write_file(
        weak_repo / "service.py",
        f"def bloated():\n    total = 0\n{weak_body}\n    return total\n",
    )

    _write_file(
        strong_repo / "service.py",
        '"""Service helpers."""\n\n'
        "def small_function() -> int:\n"
        "    return 1\n",
    )
    _write_file(
        strong_repo / "tests" / "test_service.py",
        '"""Service tests."""\n\n'
        "def test_small_function_result():\n"
        "    assert True\n",
    )

    weak_result = analyze_code_quality(str(weak_repo))
    strong_result = analyze_code_quality(str(strong_repo))

    weak_metrics = weak_result["metrics"]
    strong_metrics = strong_result["metrics"]

    for metric_name in (
        "maintainability_score",
        "complexity_score",
        "documentation_score",
        "test_coverage_estimate",
    ):
        assert 0 <= weak_metrics[metric_name] <= 100
        assert 0 <= strong_metrics[metric_name] <= 100

    assert strong_metrics["maintainability_score"] > weak_metrics["maintainability_score"]
    assert strong_metrics["complexity_score"] > weak_metrics["complexity_score"]
    assert strong_metrics["documentation_score"] > weak_metrics["documentation_score"]
    assert strong_metrics["test_coverage_estimate"] > weak_metrics["test_coverage_estimate"]
