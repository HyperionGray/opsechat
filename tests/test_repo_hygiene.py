"""
Tests for repository hygiene checker rules.
"""

import tempfile
from pathlib import Path

from scripts.check_repo_hygiene import (
    detect_redundant_directory_nesting,
    detect_stale_artifacts,
    detect_unfinished_markers,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detect_unfinished_markers_only_in_comments():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write(root / "src/app.py", "x = 1  # TODO remove hardcode\n")
        _write(root / "src/value.py", 'status = "TODO is user input"\n')
        _write(root / "docs/notes.py", "# TODO this is docs and should be ignored\n")

        issues = detect_unfinished_markers(
            root,
            [
                "src/app.py",
                "src/value.py",
                "docs/notes.py",
            ],
        )

        assert len(issues) == 1
        assert issues[0].path == "src/app.py"
        assert issues[0].line == 1


def test_detect_stale_artifacts_flags_backups_and_debug_helpers():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write(root / "Dockerfile~HEAD", "FROM scratch\n")
        _write(root / "tmp/notes.orig", "backup\n")
        _write(root / "test-server.js", "console.log('debug')\n")
        _write(root / "src/app.py", "print('ok')\n")

        issues = detect_stale_artifacts(
            root,
            [
                "Dockerfile~HEAD",
                "tmp/notes.orig",
                "test-server.js",
                "src/app.py",
            ],
        )
        paths = {issue.path for issue in issues}
        assert "Dockerfile~HEAD" in paths
        assert "tmp/notes.orig" in paths
        assert "test-server.js" in paths
        assert "src/app.py" not in paths


def test_detect_redundant_directory_nesting():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _write(root / "src/src/module.py", "pass\n")
        _write(root / "docs/implementation/guide.md", "guide\n")
        _write(root / "tests/tests/e2e.spec.js", "console.log('ok')\n")

        issues = detect_redundant_directory_nesting(
            root,
            [
                "src/src/module.py",
                "docs/implementation/guide.md",
                "tests/tests/e2e.spec.js",
            ],
        )
        paths = {issue.path for issue in issues}
        assert "src/src/module.py" in paths
        assert "tests/tests/e2e.spec.js" in paths
        assert "docs/implementation/guide.md" not in paths
