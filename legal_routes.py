"""
Public legal/policy routes for opsechat.

These endpoints render markdown policy documents from docs/legal as
read-only HTML pages:
  - /terms
  - /aup
  - /privacy
"""

import html
import os
import re
from flask import abort, render_template

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DIR = os.path.join(_BASE_DIR, "docs", "legal")

_POLICY_FILES = {
    "terms": "TERMS_OF_SERVICE.md",
    "aup": "ACCEPTABLE_USE_POLICY.md",
    "privacy": "PRIVACY_POLICY.md",
}

_POLICY_TITLES = {
    "terms": "Terms of Service",
    "aup": "Acceptable Use Policy",
    "privacy": "Privacy Policy",
}


def _format_inline(markdown_text):
    """Render a small, safe subset of inline markdown."""
    escaped = html.escape(markdown_text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    route_aliases = {
        "TERMS_OF_SERVICE.md": "/terms",
        "ACCEPTABLE_USE_POLICY.md": "/aup",
        "PRIVACY_POLICY.md": "/privacy",
    }

    def _link_replacer(match):
        label = match.group(1)
        href = match.group(2).strip()
        href = route_aliases.get(href, href)
        lowered = href.lower()
        if lowered.startswith("javascript:"):
            href = "#"
        safe_href = html.escape(href, quote=True)
        return (
            f'<a href="{safe_href}"'
            ' target="_blank" rel="noopener noreferrer">'
            f"{label}</a>"
        )

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_replacer, escaped)


def _render_markdown(markdown_text):
    """Convert policy markdown to simple HTML for legal display."""
    lines = markdown_text.splitlines()
    html_parts = []
    paragraph = []
    in_list = False

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            joined = " ".join(paragraph).strip()
            html_parts.append(f"<p>{_format_inline(joined)}</p>")
            paragraph = []

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped:
            flush_paragraph()
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if stripped == "---":
            flush_paragraph()
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr>")
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            level = min(6, len(stripped) - len(stripped.lstrip("#")))
            heading_text = stripped[level:].strip()
            html_parts.append(f"<h{level}>{_format_inline(heading_text)}</h{level}>")
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item_text = stripped[2:].strip()
            html_parts.append(f"<li>{_format_inline(item_text)}</li>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _load_policy_markdown(policy_key):
    filename = _POLICY_FILES.get(policy_key)
    if not filename:
        return None
    full_path = os.path.join(_LEGAL_DIR, filename)
    try:
        with open(full_path, "r", encoding="utf-8") as file_obj:
            return file_obj.read()
    except OSError:
        return None


def _render_policy(policy_key):
    markdown = _load_policy_markdown(policy_key)
    if markdown is None:
        abort(404)

    return render_template(
        "legal_policy.html",
        policy_key=policy_key,
        policy_title=_POLICY_TITLES[policy_key],
        policy_html=_render_markdown(markdown),
    )


def register_legal_routes(app):
    """Register public legal routes."""

    @app.route("/terms", methods=["GET"])
    def terms():
        return _render_policy("terms")

    @app.route("/aup", methods=["GET"])
    def aup():
        return _render_policy("aup")

    @app.route("/privacy", methods=["GET"])
    def privacy():
        return _render_policy("privacy")
