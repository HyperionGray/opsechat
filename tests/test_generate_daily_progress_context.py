import subprocess
import sys
from pathlib import Path


def run_report(tmp_path: Path) -> str:
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_daily_progress_context.py"
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path), "--max-items", "5"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_report_counts_code_markers_and_ignores_docs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def do_work():\n"
        "    # TODO: wire this up\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "worker.js").write_text(
        "// STUB: implement worker path\n"
        "export const ok = true;\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "README.md").write_text(
        "# TODO docs item should be ignored\n",
        encoding="utf-8",
    )

    output = run_report(tmp_path)

    assert "Total markers found: **2**" in output
    assert "- TODO: 1" in output
    assert "- STUB: 1" in output
    assert "docs/README.md" not in output


def test_report_finds_cleanup_candidates(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "workflows-sync-template-backup.yml").write_text(
        "name: backup workflow\n",
        encoding="utf-8",
    )
    (tmp_path / "module_old.py").write_text("print('legacy')\n", encoding="utf-8")

    output = run_report(tmp_path)

    assert "Potential cleanup candidates" in output
    assert ".github/workflows/workflows-sync-template-backup.yml" in output
    assert "module_old.py" in output
