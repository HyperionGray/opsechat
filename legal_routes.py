"""
Public legal policy routes for opsechat.

Serves repository-backed legal markdown documents at:
  - /terms
  - /aup
  - /privacy
"""

import os
import re
from html import escape
from flask import render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_LEGAL_DOCS = {
    "terms": ("docs/legal/TERMS_OF_SERVICE.md", "Terms of Service"),
    "aup": ("docs/legal/ACCEPTABLE_USE_POLICY.md", "Acceptable Use Policy"),
    "privacy": ("docs/legal/PRIVACY_POLICY.md", "Privacy Policy"),
}


def _markdown_to_html(markdown_text: str) -> str:
    """
    Convert a subset of Markdown into safe HTML.

    We intentionally support only simple, predictable formatting for legal docs:
    headings, horizontal rules, unordered lists, and paragraphs.
    """
    parts = []
    in_list = False

    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()

        if not stripped:
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue

        if stripped == "---":
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append("<hr>")
            continue

        if stripped.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h3>{escape(stripped[4:])}</h3>")
            continue

        if stripped.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h2>{escape(stripped[3:])}</h2>")
            continue

        if stripped.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h1>{escape(stripped[2:])}</h1>")
            continue

        if stripped.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{escape(stripped[2:])}</li>")
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False

        # Preserve numbered-list semantics without parsing nested structures.
        if re.match(r"^\d+\.\s+", stripped):
            parts.append(f"<p>{escape(stripped)}</p>")
        else:
            parts.append(f"<p>{escape(stripped)}</p>")

    if in_list:
        parts.append("</ul>")

    return "\n".join(parts)


def _render_legal_doc(doc_key: str):
    """Render a single legal document page."""
    rel_path, title = _LEGAL_DOCS[doc_key]
    abs_path = os.path.join(_BASE_DIR, rel_path)

    try:
        with open(abs_path, "r", encoding="utf-8") as legal_doc:
            markdown_text = legal_doc.read()
    except (FileNotFoundError, OSError):
        markdown_text = (
            "# Document Unavailable\n\n"
            "This legal document is currently unavailable. Please try again later."
        )

    document_html = _markdown_to_html(markdown_text)
    return render_template(
        "legal_document.html",
        page_title=title,
        source_path=rel_path,
        document_html=document_html,
    )


def register_legal_routes(app):
    """Register public legal policy endpoints."""

    @app.route("/terms", methods=["GET"])
    def terms_page():
        return _render_legal_doc("terms")

    @app.route("/aup", methods=["GET"])
    def aup_page():
        return _render_legal_doc("aup")

    @app.route("/privacy", methods=["GET"])
    def privacy_page():
        return _render_legal_doc("privacy")
