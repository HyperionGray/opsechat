"""
Legal policy routes for opsechat.

Provides public pages for Terms of Service, Privacy Policy, and
Acceptable Use Policy. Source documents live in docs/legal/*.md.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
import re

from flask import current_app, render_template


REPO_ROOT = Path(__file__).resolve().parent
LEGAL_DOCS = {
    "terms": {
        "title": "Terms of Service",
        "filename": "TERMS_OF_SERVICE.md",
    },
    "privacy": {
        "title": "Privacy Policy",
        "filename": "PRIVACY_POLICY.md",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "filename": "ACCEPTABLE_USE_POLICY.md",
    },
}


def _rewrite_legal_link(target: str) -> str:
    """Map in-doc markdown links to canonical policy routes."""
    normalized = target.strip().lower()
    if normalized.endswith("terms_of_service.md"):
        return "/terms"
    if normalized.endswith("acceptable_use_policy.md"):
        return "/aup"
    if normalized.endswith("privacy_policy.md"):
        return "/privacy"
    return target


def _render_inline_markdown(text: str) -> str:
    """Render a small, safe subset of markdown inline elements."""
    rendered = escape(text)

    # [text](url)
    def _replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        target = _rewrite_legal_link(match.group(2))
        safe_target = escape(target, quote=True)
        return f'<a href="{safe_target}" rel="noopener noreferrer">{label}</a>'

    rendered = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, rendered)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", rendered)
    return rendered


def _render_markdown_to_html(markdown_text: str) -> str:
    """
    Render markdown to HTML using a constrained subset.

    This avoids an extra dependency while still providing readable policy pages.
    """
    lines = markdown_text.splitlines()
    html_parts = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            close_list()
            continue

        if line == "---":
            close_list()
            html_parts.append("<hr>")
            continue

        if line.startswith("### "):
            close_list()
            html_parts.append(f"<h3>{_render_inline_markdown(line[4:])}</h3>")
            continue

        if line.startswith("## "):
            close_list()
            html_parts.append(f"<h2>{_render_inline_markdown(line[3:])}</h2>")
            continue

        if line.startswith("# "):
            close_list()
            html_parts.append(f"<h1>{_render_inline_markdown(line[2:])}</h1>")
            continue

        if line.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_render_inline_markdown(line[2:])}</li>")
            continue

        close_list()
        html_parts.append(f"<p>{_render_inline_markdown(line)}</p>")

    close_list()
    return "\n".join(html_parts)


def _load_legal_document(doc_key: str) -> tuple[str, str]:
    """
    Load the markdown document and return (title, rendered_html).
    """
    if doc_key not in LEGAL_DOCS:
        raise KeyError(f"Unknown legal document key: {doc_key}")

    doc_meta = LEGAL_DOCS[doc_key]
    document_path = REPO_ROOT / "docs" / "legal" / doc_meta["filename"]
    if not document_path.exists():
        current_app.logger.error("Missing legal document: %s", document_path)
        return doc_meta["title"], "<p>Document is temporarily unavailable.</p>"

    markdown_text = document_path.read_text(encoding="utf-8")
    return doc_meta["title"], _render_markdown_to_html(markdown_text)


def register_legal_routes(app):
    """Register legal policy pages."""

    @app.route("/terms", methods=["GET"])
    def legal_terms():
        title, content_html = _load_legal_document("terms")
        return render_template(
            "legal_document.html",
            page_title=title,
            content_html=content_html,
            current_doc="terms",
        )

    @app.route("/privacy", methods=["GET"])
    def legal_privacy():
        title, content_html = _load_legal_document("privacy")
        return render_template(
            "legal_document.html",
            page_title=title,
            content_html=content_html,
            current_doc="privacy",
        )

    @app.route("/aup", methods=["GET"])
    def legal_aup():
        title, content_html = _load_legal_document("aup")
        return render_template(
            "legal_document.html",
            page_title=title,
            content_html=content_html,
            current_doc="aup",
        )
