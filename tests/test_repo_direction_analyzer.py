from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repo_direction_analyzer as analyzer  # noqa: E402


def test_top_level_area_maps_root_and_nested_paths():
    assert analyzer.top_level_area("README.md") == "root"
    assert analyzer.top_level_area(".github/workflows/ci.yml") == ".github"
    assert analyzer.top_level_area("docs/README.md") == "docs"


def test_summarize_focus_counts_top_areas():
    paths = [
        ".github/workflows/ci.yml",
        ".github/workflows/python-tests.yml",
        "docs/README.md",
        "tests/test_rate_limiter.py",
        "tests/test_imports.py",
        "README.md",
    ]
    focus = analyzer.summarize_focus(paths, limit=3)
    assert focus[0] == (".github", 2)
    assert ("tests", 2) in focus


def test_find_hygiene_warnings_detects_nested_paths():
    warnings = analyzer.find_hygiene_warnings(
        [
            ".github/.github/workflows/workflows-sync.yml",
            "docs/README.md",
        ]
    )
    assert any(".github/.github" in warning for warning in warnings)


def test_render_markdown_includes_all_sections():
    markdown = analyzer.render_markdown(
        commits=[("abcdef123456", "Improve workflow reliability")],
        focus=[(".github", 3), ("tests", 2)],
        warnings=["Nested '.github/.github' directory detected."],
        steps=["Strengthen workflow reliability with tighter triggers."],
    )
    assert "## Repository Direction Summary" in markdown
    assert "### Recent commits" in markdown
    assert "### Hot areas (recently touched)" in markdown
    assert "### Suggested next steps" in markdown
    assert "### Hygiene warnings" in markdown
