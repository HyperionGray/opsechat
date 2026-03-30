"""
Legal policy routes for opsechat.

Serves the repository's legal markdown documents as read-only pages at:
- /terms
- /privacy
- /aup
"""

import os
from flask import abort, render_template

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DOCS_DIR = os.path.join(_BASE_DIR, "docs", "legal")

_LEGAL_DOCUMENTS = {
    "terms": {
        "title": "Terms of Service",
        "filename": "TERMS_OF_SERVICE.md",
        "route": "/terms",
    },
    "privacy": {
        "title": "Privacy Policy",
        "filename": "PRIVACY_POLICY.md",
        "route": "/privacy",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "filename": "ACCEPTABLE_USE_POLICY.md",
        "route": "/aup",
    },
}


def _load_legal_markdown(filename):
    """Load a legal markdown file from docs/legal."""
    path = os.path.join(_LEGAL_DOCS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def _render_legal_document(doc_key):
    config = _LEGAL_DOCUMENTS[doc_key]
    content = _load_legal_markdown(config["filename"])
    if content is None:
        abort(404)

    nav_links = [
        {
            "title": item["title"],
            "route": item["route"],
            "active": key == doc_key,
        }
        for key, item in _LEGAL_DOCUMENTS.items()
    ]

    return render_template(
        "legal_document.html",
        title=config["title"],
        content=content,
        source_path=f"docs/legal/{config['filename']}",
        nav_links=nav_links,
    )


def register_legal_routes(app):
    """Register public legal policy pages."""

    def _make_view(doc_key):
        def _view():
            return _render_legal_document(doc_key)

        _view.__name__ = f"legal_{doc_key}"
        return _view

    for doc_key, config in _LEGAL_DOCUMENTS.items():
        app.add_url_rule(
            config["route"],
            endpoint=f"legal_{doc_key}",
            view_func=_make_view(doc_key),
            strict_slashes=False,
        )
