"""
Legal policy routes for public policy pages.

Provides:
- /terms   -> Terms of Service
- /aup     -> Acceptable Use Policy
- /privacy -> Privacy Policy
"""

import html
import os
import re
from flask import abort, render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LEGAL_DOCS = {
    "terms": {
        "title": "Terms of Service",
        "filename": "TERMS_OF_SERVICE.md",
        "summary": "Service terms and legal obligations for using OpSecChat.",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "filename": "ACCEPTABLE_USE_POLICY.md",
        "summary": "Rules for lawful and safe use of OpSecChat.",
    },
    "privacy": {
        "title": "Privacy Policy",
        "filename": "PRIVACY_POLICY.md",
        "summary": "How OpSecChat handles data, retention, and privacy controls.",
    },
}

_INTERNAL_DOC_LINKS = {
    "TERMS_OF_SERVICE.md": "/terms",
    "ACCEPTABLE_USE_POLICY.md": "/aup",
    "PRIVACY_POLICY.md": "/privacy",
}

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")


def _read_version() -> str:
    """Read VERSION from repository root, with a stable fallback."""
    try:
        with open(os.path.join(_BASE_DIR, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.8.0-alpha"


def _map_doc_link(url: str) -> str:
    """Map internal markdown doc links to public route paths."""
    normalized = url.strip().replace("./", "")
    mapped = _INTERNAL_DOC_LINKS.get(normalized, normalized)
    if mapped.startswith(("/", "http://", "https://")):
        return mapped
    return "#"


def _render_inline_markdown(text: str) -> str:
    """Render a small markdown subset (links, emphasis, inline code)."""
    escaped = html.escape(text)

    def _replace_link(match: re.Match) -> str:
        # `escaped` text has already been escaped once above.
        label = match.group(1)
        target = html.escape(_map_doc_link(html.unescape(match.group(2))), quote=True)
        return f'<a href="{target}">{label}</a>'

    rendered = _LINK_RE.sub(_replace_link, escaped)
    rendered = _BOLD_RE.sub(r"<strong>\1</strong>", rendered)
    rendered = _ITALIC_RE.sub(r"<em>\1</em>", rendered)
    rendered = _CODE_RE.sub(r"<code>\1</code>", rendered)
    return rendered


def _markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown to safe HTML using a conservative subset.

    This keeps dependencies minimal while providing readable policy pages.
    """
    lines = markdown_text.splitlines()
    chunks = []
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            chunks.append("</ul>")
            in_ul = False
        if in_ol:
            chunks.append("</ol>")
            in_ol = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            close_lists()
            continue

        if stripped in ("---", "***"):
            close_lists()
            chunks.append("<hr>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_lists()
            level = len(heading.group(1))
            chunks.append(
                f"<h{level}>{_render_inline_markdown(heading.group(2).strip())}</h{level}>"
            )
            continue

        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        if unordered:
            if in_ol:
                chunks.append("</ol>")
                in_ol = False
            if not in_ul:
                chunks.append("<ul>")
                in_ul = True
            chunks.append(f"<li>{_render_inline_markdown(unordered.group(1).strip())}</li>")
            continue

        ordered = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if ordered:
            if in_ul:
                chunks.append("</ul>")
                in_ul = False
            if not in_ol:
                chunks.append("<ol>")
                in_ol = True
            chunks.append(f"<li>{_render_inline_markdown(ordered.group(1).strip())}</li>")
            continue

        close_lists()
        chunks.append(f"<p>{_render_inline_markdown(stripped)}</p>")

    close_lists()
    return "\n".join(chunks)


def _read_legal_markdown(filename: str) -> str:
    """Load legal markdown content from docs/legal."""
    path = os.path.join(_BASE_DIR, "docs", "legal", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _render_policy(policy_key: str):
    """Render a policy page by key from LEGAL_DOCS."""
    config = LEGAL_DOCS.get(policy_key)
    if not config:
        abort(404)

    try:
        markdown_content = _read_legal_markdown(config["filename"])
    except OSError:
        abort(503, description="Policy document is temporarily unavailable.")

    return render_template(
        "policy_page.html",
        page_title=config["title"],
        page_summary=config["summary"],
        policy_key=policy_key,
        policy_html=_markdown_to_html(markdown_content),
        version=_read_version(),
    )


def register_legal_routes(app):
    """Register public legal policy routes."""

    @app.route("/terms", methods=["GET"])
    def terms_of_service():
        return _render_policy("terms")

    @app.route("/aup", methods=["GET"])
    def acceptable_use_policy():
        return _render_policy("aup")

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        return _render_policy("privacy")
