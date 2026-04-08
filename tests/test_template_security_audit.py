"""
Tests for template security auditing and enforcement.
"""

import logging
from pathlib import Path

import pytest

from template_security_audit import (
    enforce_template_security_audit,
    scan_template_security,
)


def _write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def test_scan_template_security_detects_inline_constructs(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()

    _write(
        templates / "unsafe.html",
        """<html>
<head><script>alert("x")</script></head>
<body style="color: red" onclick="doThing()"><style>.a{color:red}</style></body>
</html>""",
    )
    _write(
        templates / "safe.html",
        """<html><head><script src="/static/app.js"></script></head><body></body></html>""",
    )

    report = scan_template_security(str(templates), use_cache=False)
    assert report.has_issues() is True
    assert "unsafe.html" in report.issues_by_file
    assert "safe.html" not in report.issues_by_file

    issue_types = {issue.issue_type for issue in report.issues_by_file["unsafe.html"]}
    assert "inline-script" in issue_types
    assert "inline-style-attr" in issue_types
    assert "inline-style-tag" in issue_types
    assert "inline-event-handler" in issue_types


def test_enforce_template_security_audit_warn_mode_logs_warning(tmp_path, caplog):
    templates = tmp_path / "templates"
    templates.mkdir()
    _write(templates / "unsafe.html", "<script>alert(1)</script>")

    caplog.set_level(logging.WARNING, logger="template-security-audit-test")
    logger = logging.getLogger("template-security-audit-test")

    report = enforce_template_security_audit(
        str(templates),
        mode="warn",
        logger=logger,
    )
    assert report.has_issues() is True
    assert "Template security audit found" in caplog.text


def test_enforce_template_security_audit_strict_mode_raises(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    _write(templates / "unsafe.html", "<div style='color: red'>x</div>")

    with pytest.raises(RuntimeError):
        enforce_template_security_audit(str(templates), mode="strict")


def test_enforce_template_security_audit_off_mode_skips_scan(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    _write(templates / "unsafe.html", "<script>alert(1)</script>")

    report = enforce_template_security_audit(str(templates), mode="off")
    assert report.has_issues() is False
    assert report.issue_count == 0


def test_enforce_template_security_audit_supports_exclusions(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    _write(templates / "legacy.html", "<script>alert(1)</script>")

    report = enforce_template_security_audit(
        str(templates),
        mode="warn",
        exclude_files=["legacy.html"],
    )
    assert report.has_issues() is False
