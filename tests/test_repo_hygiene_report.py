import importlib.util
from pathlib import Path


def load_report_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "repo_hygiene_report.py"
    spec = importlib.util.spec_from_file_location("repo_hygiene_report", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_find_unfinished_markers_ignores_docs_and_bak(tmp_path):
    mod = load_report_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "bak").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1  # TODO: finish\n", encoding="utf-8")
    (tmp_path / "docs" / "note.md").write_text("TODO should be ignored\n", encoding="utf-8")
    (tmp_path / "bak" / "old.py").write_text("# FIXME ignored\n", encoding="utf-8")

    markers = mod.find_unfinished_markers(tmp_path)
    assert len(markers) == 1
    assert markers[0].path == "src/app.py"
    assert markers[0].line == 1


def test_find_python_stub_functions_detects_pass_only_functions(tmp_path):
    mod = load_report_module()
    source = (
        "def real_fn():\n"
        "    return 1\n\n"
        "def stub_fn():\n"
        "    pass\n\n"
        "class C:\n"
        "    async def async_stub(self):\n"
        "        ...\n"
    )
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")

    stubs = mod.find_python_stub_functions(tmp_path)
    names = {(item.name, item.line) for item in stubs}
    assert ("stub_fn", 4) in names
    assert ("async_stub", 8) in names
    assert all(name != "real_fn" for name, _ in names)


def test_build_report_has_expected_sections():
    mod = load_report_module()
    report = mod.build_report(
        markers=[],
        stubs=[],
        cleanup_candidates=["tests/mock_server_refactored.py (duplicate pattern)"],
        commit_messages=["Sync workflow templates", "Add ci status report"],
        max_items=10,
    )

    assert "# Repository Hygiene Report" in report
    assert "## Unfinished Markers" in report
    assert "## Python Stub Functions" in report
    assert "## Cleanup Candidates" in report
    assert "## Suggested Next Step" in report
