"""
Legal document routes for opsechat.

Provides user-facing policy pages:
  - /terms
  - /aup
  - /privacy
"""

import html
import os
import re
from flask import abort, render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DOCS_DIR = os.path.join(_BASE_DIR, "docs", "legal")
_MD_ROUTE_MAP = {
    "TERMS_OF_SERVICE.md": "/terms",
    "ACCEPTABLE_USE_POLICY.md": "/aup",
    "PRIVACY_POLICY.md": "/privacy",
    "docs/legal/TERMS_OF_SERVICE.md": "/terms",
    "docs/legal/ACCEPTABLE_USE_POLICY.md": "/aup",
    "docs/legal/PRIVACY_POLICY.md": "/privacy",
}

LEGAL_PAGES = (
    {
        "slug": "terms",
        "route": "/terms",
        "title": "Terms of Service",
        "filename": "TERMS_OF_SERVICE.md",
    },
    {
        "slug": "aup",
        "route": "/aup",
        "title": "Acceptable Use Policy",
        "filename": "ACCEPTABLE_USE_POLICY.md",
    },
    {
        "slug": "privacy",
        "route": "/privacy",
        "title": "Privacy Policy",
        "filename": "PRIVACY_POLICY.md",
    },
)

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"\*([^*]+)\*")


def _render_inline(markdown_text):
    """Render a small, safe subset of inline markdown to HTML."""
    escaped = html.escape(markdown_text, quote=True)

    def _link_repl(match):
        label = html.escape(match.group(1), quote=True)
        href_raw = match.group(2).strip()
        if href_raw in _MD_ROUTE_MAP:
            href_raw = _MD_ROUTE_MAP[href_raw]
        if ":" in href_raw and not (
            href_raw.startswith("http://") or href_raw.startswith("https://")
        ):
            href_raw = "#"
        href = html.escape(href_raw, quote=True)
        attrs = ""
        if href.startswith("http://") or href.startswith("https://"):
            attrs = ' target="_blank" rel="noopener noreferrer"'
        return f'<a href="{href}"{attrs}>{label}</a>'

    text = _LINK_RE.sub(_link_repl, escaped)
    text = _INLINE_CODE_RE.sub(r"<code>\1</code>", text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    return text


def _markdown_to_html(markdown_text):
    """
    Convert markdown to safe HTML for policy pages.

    This intentionally supports a small subset that covers our legal docs:
    headings, paragraphs, horizontal rules, and lists.
    """
    output = []
    in_ul = False
    in_ol = False

    def _close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            output.append("</ul>")
            in_ul = False
        if in_ol:
            output.append("</ol>")
            in_ol = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            _close_lists()
            continue

        if stripped == "---":
            _close_lists()
            output.append("<hr>")
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            _close_lists()
            level = len(heading_match.group(1))
            heading_text = _render_inline(heading_match.group(2).strip())
            output.append(f"<h{level}>{heading_text}</h{level}>")
            continue

        ul_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if ul_match:
            if in_ol:
                output.append("</ol>")
                in_ol = False
            if not in_ul:
                output.append("<ul>")
                in_ul = True
            output.append(f"<li>{_render_inline(ul_match.group(1).strip())}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            if in_ul:
                output.append("</ul>")
                in_ul = False
            if not in_ol:
                output.append("<ol>")
                in_ol = True
            output.append(f"<li>{_render_inline(ol_match.group(1).strip())}</li>")
            continue

        _close_lists()
        output.append(f"<p>{_render_inline(stripped)}</p>")

    _close_lists()
    return "\n".join(output)


def _load_document_or_404(filename):
    path = os.path.join(_LEGAL_DOCS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return file_obj.read()
    except (FileNotFoundError, OSError):
        abort(404)


def register_legal_routes(app):
    """Register legal policy pages."""

    for page in LEGAL_PAGES:
        route = page["route"]
        endpoint = f"legal_{page['slug']}"
        title = page["title"]
        filename = page["filename"]

        def _view(page_title=title, page_filename=filename):
            markdown_text = _load_document_or_404(page_filename)
            return render_template(
                "legal_document.html",
                page_title=page_title,
                document_html=_markdown_to_html(markdown_text),
            )

        app.add_url_rule(route, endpoint=endpoint, view_func=_view, strict_slashes=False)
