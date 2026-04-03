"""
Legal policy routes for opsechat.

Exposes simple public pages for Terms, Acceptable Use Policy, and Privacy
Policy so policy docs are available directly from the running application.
"""

from pathlib import Path
from flask import render_template


_BASE_DIR = Path(__file__).resolve().parent
_LEGAL_DOCS_DIR = _BASE_DIR / "docs" / "legal"

_POLICIES = {
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


def _load_policy_text(filename: str) -> str:
    """
    Load policy markdown content from docs/legal.

    Returns an empty string if the file is missing or unreadable.
    """
    try:
        return (_LEGAL_DOCS_DIR / filename).read_text(encoding="utf-8")
    except OSError:
        return ""


def _render_policy(policy_key: str):
    """Render a legal policy page by policy key."""
    policy = _POLICIES[policy_key]
    content = _load_policy_text(policy["filename"])

    if not content:
        return render_template(
            "legal_document.html",
            title=policy["title"],
            content="This policy document is currently unavailable.",
            available=False,
        ), 503

    return render_template(
        "legal_document.html",
        title=policy["title"],
        content=content,
        available=True,
    )


def register_legal_routes(app):
    """Register legal policy endpoints with the Flask app."""

    @app.route("/terms", methods=["GET"])
    def terms_of_service():
        return _render_policy("terms")

    @app.route("/aup", methods=["GET"])
    def acceptable_use_policy():
        return _render_policy("aup")

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        return _render_policy("privacy")
