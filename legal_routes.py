"""
Legal policy routes for opsechat.

Serves project legal documents as simple HTML pages so policy links can be
shared directly in release and signup flows.
"""

from pathlib import Path
from flask import render_template


LEGAL_DOCS = {
    "terms": {
        "title": "Terms of Service",
        "filename": "TERMS_OF_SERVICE.md",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "filename": "ACCEPTABLE_USE_POLICY.md",
    },
    "privacy": {
        "title": "Privacy Policy",
        "filename": "PRIVACY_POLICY.md",
    },
}


def _legal_doc_path(filename):
    """Return absolute path to a legal markdown file."""
    repo_root = Path(__file__).resolve().parent
    return repo_root / "docs" / "legal" / filename


def _read_doc_or_none(filename):
    """Read legal markdown content, returning None if unavailable."""
    doc_path = _legal_doc_path(filename)
    try:
        return doc_path.read_text(encoding="utf-8")
    except OSError:
        return None


def register_legal_routes(app):
    """Register legal policy endpoints on the Flask app."""

    @app.route("/terms", methods=["GET"])
    def terms_of_service():
        doc = _read_doc_or_none(LEGAL_DOCS["terms"]["filename"])
        if doc is None:
            return ("", 404)
        return render_template(
            "legal_policy.html",
            policy_title=LEGAL_DOCS["terms"]["title"],
            policy_text=doc,
        )

    @app.route("/aup", methods=["GET"])
    def acceptable_use_policy():
        doc = _read_doc_or_none(LEGAL_DOCS["aup"]["filename"])
        if doc is None:
            return ("", 404)
        return render_template(
            "legal_policy.html",
            policy_title=LEGAL_DOCS["aup"]["title"],
            policy_text=doc,
        )

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        doc = _read_doc_or_none(LEGAL_DOCS["privacy"]["filename"])
        if doc is None:
            return ("", 404)
        return render_template(
            "legal_policy.html",
            policy_title=LEGAL_DOCS["privacy"]["title"],
            policy_text=doc,
        )
