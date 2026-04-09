"""
Legal policy routes for opsechat.

Serves Terms of Service, Privacy Policy, and Acceptable Use Policy pages
directly from the canonical markdown documents in docs/legal/.
"""

from __future__ import annotations

import html
import os
import re
from flask import render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DOCS_DIR = os.path.join(_BASE_DIR, "docs", "legal")


def _inline_markdown(text: str) -> str:
    """Render a small markdown subset used by policy docs."""
    escaped = html.escape(text)
    escaped = _rewrite_policy_links(escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[(.+?)\]\((.+?)\)",
        lambda m: f'<a href="{_map_markdown_href(m.group(2))}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def _rewrite_policy_links(text: str) -> str:
    """Rewrite bare policy markdown file references into route links."""
    mappings = {
        "TERMS_OF_SERVICE.md": "/terms",
        "PRIVACY_POLICY.md": "/privacy",
        "ACCEPTABLE_USE_POLICY.md": "/aup",
    }
    for source, target in mappings.items():
        text = text.replace(source, target)
    return text


def _map_markdown_href(href: str) -> str:
    """Map known markdown policy links to application routes."""
    normalized = href.strip()
    if normalized.endswith("TERMS_OF_SERVICE.md"):
        return "/terms"
    if normalized.endswith("PRIVACY_POLICY.md"):
        return "/privacy"
    if normalized.endswith("ACCEPTABLE_USE_POLICY.md"):
        return "/aup"
    return normalized


def _markdown_to_html(markdown_text: str) -> str:
    """Convert policy markdown to safe, readable HTML.

    This intentionally supports a constrained markdown subset:
    headings, horizontal rules, unordered lists, and paragraphs.
    """
    lines = markdown_text.splitlines()
    output = []
    in_list = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            if in_list:
                output.append("</ul>")
                in_list = False
            continue

        if line == "---":
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append("<hr>")
            continue

        if line.startswith("### "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h3>{_inline_markdown(line[4:])}</h3>")
            continue

        if line.startswith("## "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h2>{_inline_markdown(line[3:])}</h2>")
            continue

        if line.startswith("# "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h1>{_inline_markdown(line[2:])}</h1>")
            continue

        if line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{_inline_markdown(line[2:])}</li>")
            continue

        if in_list:
            output.append("</ul>")
            in_list = False

        output.append(f"<p>{_inline_markdown(line)}</p>")

    if in_list:
        output.append("</ul>")

    return "\n".join(output)


def _load_policy_document(filename: str) -> tuple[str, str]:
    """Load a markdown policy document and return (title, html_content)."""
    path = os.path.join(_LEGAL_DOCS_DIR, filename)
    with open(path, "r", encoding="utf-8") as fh:
        markdown_text = fh.read()

    title = "Policy"
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return title, _markdown_to_html(markdown_text)


def register_legal_routes(app):
    """Register legal policy routes with the Flask app."""

    @app.route("/terms", methods=["GET"])
    def terms_page():
        title, content_html = _load_policy_document("TERMS_OF_SERVICE.md")
        return render_template(
            "legal_policy.html",
            page_title=title,
            content_html=content_html,
            source_path="docs/legal/TERMS_OF_SERVICE.md",
        )

    @app.route("/privacy", methods=["GET"])
    def privacy_page():
        title, content_html = _load_policy_document("PRIVACY_POLICY.md")
        return render_template(
            "legal_policy.html",
            page_title=title,
            content_html=content_html,
            source_path="docs/legal/PRIVACY_POLICY.md",
        )

    @app.route("/aup", methods=["GET"])
    def aup_page():
        title, content_html = _load_policy_document("ACCEPTABLE_USE_POLICY.md")
        return render_template(
            "legal_policy.html",
            page_title=title,
            content_html=content_html,
            source_path="docs/legal/ACCEPTABLE_USE_POLICY.md",
        )
