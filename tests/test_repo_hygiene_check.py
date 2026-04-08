from pathlib import Path

from scripts.repo_hygiene_check import scan_repo


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_repo_detects_expected_hygiene_findings(tmp_path: Path) -> None:
    _write(tmp_path / "Dockerfile~HEAD", "backup")
    _write(
        tmp_path / ".github/.github/workflows/placeholder.yml",
        "# Placeholder workflow for nested file\n",
    )
    _write(tmp_path / ".github/workflows/active-placeholder.yml", "# Placeholder workflow\n")
    _write(tmp_path / "src/module.py", "# TODO: finish implementation\nprint('ok')\n")
    _write(tmp_path / ".github/d", "")

    findings = scan_repo(tmp_path)
    categories = {f.category for f in findings}

    assert "backup-file" in categories
    assert "nested-workflow" in categories
    assert "placeholder-workflow" in categories
    assert "unfinished-marker" in categories
    assert "zero-byte-file" in categories


def test_scan_repo_ignores_unfinished_keywords_in_code(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts/repo_hygiene_check.py",
        "UNFINISHED_RE = re.compile(r'TODO|FIXME')\n",
    )
    findings = scan_repo(tmp_path)
    unfinished = [f for f in findings if f.category == "unfinished-marker"]
    assert unfinished == []
