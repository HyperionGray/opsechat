"""Legal policy routes for Terms, Privacy, and AUP pages."""

import os
from flask import render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DIR = os.path.join(_BASE_DIR, "docs", "legal")

POLICY_DOCS = {
    "terms": ("Terms of Service", "TERMS_OF_SERVICE.md"),
    "privacy": ("Privacy Policy", "PRIVACY_POLICY.md"),
    "aup": ("Acceptable Use Policy", "ACCEPTABLE_USE_POLICY.md"),
}


def _load_policy_doc(policy_key):
    """Load policy markdown text and an HTTP status code."""
    title, filename = POLICY_DOCS[policy_key]
    source_path = os.path.join("docs", "legal", filename)
    full_path = os.path.join(_LEGAL_DIR, filename)

    try:
        with open(full_path, "r", encoding="utf-8") as policy_file:
            return title, source_path, policy_file.read(), 200
    except OSError:
        return (
            title,
            source_path,
            "Policy document temporarily unavailable.\n\n"
            "Please try again later or contact a repository maintainer.",
            503,
        )


def _render_policy_page(policy_key):
    title, source_path, policy_text, status_code = _load_policy_doc(policy_key)
    return (
        render_template(
            "legal_policy.html",
            page_title=title,
            source_path=source_path,
            policy_text=policy_text,
            active_policy=policy_key,
        ),
        status_code,
    )


def register_legal_routes(app):
    """Register legal policy routes with the Flask app."""

    @app.route("/terms", strict_slashes=False)
    def terms_policy():
        return _render_policy_page("terms")

    @app.route("/privacy", strict_slashes=False)
    def privacy_policy():
        return _render_policy_page("privacy")

    @app.route("/aup", strict_slashes=False)
    def acceptable_use_policy():
        return _render_policy_page("aup")
