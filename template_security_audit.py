"""
Template security auditing utilities.

Scans Jinja/HTML templates for constructs that violate a strict CSP policy:
- inline <script> blocks (without src=)
- inline <style> blocks
- inline style= attributes
- inline event handlers (onclick=, onload=, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Tuple


INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
INLINE_STYLE_TAG_RE = re.compile(r"<style\b[^>]*>", re.IGNORECASE)
INLINE_STYLE_ATTR_RE = re.compile(r"\sstyle\s*=", re.IGNORECASE)
INLINE_EVENT_HANDLER_RE = re.compile(r"\son[a-zA-Z]+\s*=", re.IGNORECASE)

DEFAULT_TEMPLATE_EXTENSIONS: Tuple[str, ...] = (".html", ".htm", ".jinja2")

_SCAN_CACHE: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...]], "TemplateAuditReport"] = {}


@dataclass(frozen=True)
class TemplateIssue:
    """Single template issue."""

    line: int
    issue_type: str
    snippet: str


@dataclass
class TemplateAuditReport:
    """Template audit report."""

    issues_by_file: Dict[str, List[TemplateIssue]]

    @property
    def file_count(self) -> int:
        return len(self.issues_by_file)

    @property
    def issue_count(self) -> int:
        return sum(len(issues) for issues in self.issues_by_file.values())

    def has_issues(self) -> bool:
        return self.issue_count > 0

    def format_summary(self, max_files: int = 12) -> str:
        """Render a concise human-readable summary."""
        if not self.has_issues():
            return "Template security audit passed: no inline script/style violations found."

        lines = [
            (
                "Template security audit found "
                f"{self.issue_count} issue(s) across {self.file_count} template file(s)."
            )
        ]
        ordered = sorted(
            self.issues_by_file.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
        for file_name, issues in ordered[:max_files]:
            lines.append(f" - {file_name}: {len(issues)} issue(s)")
        remaining = self.file_count - min(self.file_count, max_files)
        if remaining > 0:
            lines.append(f" - ... and {remaining} more file(s)")
        return "\n".join(lines)


def _normalize_excludes(exclude_files: Optional[Iterable[str]]) -> Tuple[str, ...]:
    if not exclude_files:
        return tuple()
    return tuple(sorted({item.strip() for item in exclude_files if item and item.strip()}))


def _iter_template_files(
    template_dir: Path,
    extensions: Tuple[str, ...],
    exclude_files: Tuple[str, ...],
):
    exclude_set = set(exclude_files)
    for path in sorted(template_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        rel = str(path.relative_to(template_dir))
        if rel in exclude_set:
            continue
        yield path, rel


def _scan_template_content(content: str) -> List[TemplateIssue]:
    issues: List[TemplateIssue] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        snippet = line.strip()
        if not snippet:
            continue
        if INLINE_SCRIPT_RE.search(line):
            issues.append(TemplateIssue(line=line_no, issue_type="inline-script", snippet=snippet))
        if INLINE_STYLE_TAG_RE.search(line):
            issues.append(TemplateIssue(line=line_no, issue_type="inline-style-tag", snippet=snippet))
        if INLINE_STYLE_ATTR_RE.search(line):
            issues.append(TemplateIssue(line=line_no, issue_type="inline-style-attr", snippet=snippet))
        if INLINE_EVENT_HANDLER_RE.search(line):
            issues.append(TemplateIssue(line=line_no, issue_type="inline-event-handler", snippet=snippet))
    return issues


def scan_template_security(
    template_dir: str,
    *,
    exclude_files: Optional[Iterable[str]] = None,
    use_cache: bool = True,
) -> TemplateAuditReport:
    """
    Scan templates for CSP-unfriendly inline script/style usage.
    """
    root = Path(template_dir)
    if not root.exists():
        return TemplateAuditReport(issues_by_file={})

    normalized_excludes = _normalize_excludes(exclude_files)
    cache_key = (
        str(root.resolve()),
        DEFAULT_TEMPLATE_EXTENSIONS,
        normalized_excludes,
    )
    if use_cache and cache_key in _SCAN_CACHE:
        return _SCAN_CACHE[cache_key]

    issues_by_file: Dict[str, List[TemplateIssue]] = {}
    for template_path, rel_path in _iter_template_files(
        root,
        DEFAULT_TEMPLATE_EXTENSIONS,
        normalized_excludes,
    ):
        try:
            content = template_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        issues = _scan_template_content(content)
        if issues:
            issues_by_file[rel_path] = issues

    report = TemplateAuditReport(issues_by_file=issues_by_file)
    if use_cache:
        _SCAN_CACHE[cache_key] = report
    return report


def enforce_template_security_audit(
    template_dir: str,
    *,
    mode: str = "warn",
    logger=None,
    exclude_files: Optional[Iterable[str]] = None,
) -> TemplateAuditReport:
    """
    Run template audit in one of three modes:
      - off: skip audit
      - warn: log warning when issues are found
      - strict: raise RuntimeError when issues are found
    """
    normalized_mode = (mode or "warn").strip().lower()
    if normalized_mode not in {"off", "warn", "strict"}:
        raise ValueError(
            "Invalid TEMPLATE_AUDIT_MODE. Expected one of: off, warn, strict."
        )

    if normalized_mode == "off":
        return TemplateAuditReport(issues_by_file={})

    report = scan_template_security(
        template_dir,
        exclude_files=exclude_files,
    )
    if not report.has_issues():
        if logger:
            logger.info(report.format_summary())
        return report

    summary = report.format_summary()
    if normalized_mode == "strict":
        raise RuntimeError(summary)
    if logger:
        logger.warning(summary)
    return report
