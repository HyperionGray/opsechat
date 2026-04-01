"""
Legal policy routes for opsechat.

Provides read-only pages for:
- Terms of Service
- Privacy Policy
- Acceptable Use Policy
"""

from pathlib import Path
from flask import current_app, render_template


LEGAL_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "legal"


def _read_legal_doc(filename):
    """Read a legal markdown file and return plain text content."""
    doc_path = LEGAL_DOCS_DIR / filename
    try:
        return doc_path.read_text(encoding="utf-8")
    except OSError:
        return f"Document unavailable: {filename}"


def _validate_scoped_path_or_404(url_addition):
    """
    Validate path-scoped routes (/<path>/terms, etc).

    Returns True when route is valid, False when it should return 404.
    """
    configured_path = current_app.config.get("path")
    if not configured_path:
        return False
    return url_addition == configured_path


def register_legal_routes(app):
    """Register legal policy endpoints."""

    def _render_legal_page(title, filename, endpoint_prefix=""):
        base_path = endpoint_prefix.rstrip("/")
        return render_template(
            "legal_page.html",
            title=title,
            policy_text=_read_legal_doc(filename),
            nav_terms=f"{base_path}/terms" if base_path else "/terms",
            nav_privacy=f"{base_path}/privacy" if base_path else "/privacy",
            nav_aup=f"{base_path}/aup" if base_path else "/aup",
            nav_home=f"/{base_path.strip('/')}" if base_path else "/",
        )

    @app.route("/terms", methods=["GET"])
    def terms():
        return _render_legal_page("Terms of Service", "TERMS_OF_SERVICE.md")

    @app.route("/privacy", methods=["GET"])
    def privacy():
        return _render_legal_page("Privacy Policy", "PRIVACY_POLICY.md")

    @app.route("/aup", methods=["GET"])
    def aup():
        return _render_legal_page("Acceptable Use Policy", "ACCEPTABLE_USE_POLICY.md")

    @app.route("/<string:url_addition>/terms", methods=["GET"])
    def terms_scoped(url_addition):
        if not _validate_scoped_path_or_404(url_addition):
            return ("", 404)
        return _render_legal_page(
            "Terms of Service",
            "TERMS_OF_SERVICE.md",
            endpoint_prefix=f"/{url_addition}",
        )

    @app.route("/<string:url_addition>/privacy", methods=["GET"])
    def privacy_scoped(url_addition):
        if not _validate_scoped_path_or_404(url_addition):
            return ("", 404)
        return _render_legal_page(
            "Privacy Policy",
            "PRIVACY_POLICY.md",
            endpoint_prefix=f"/{url_addition}",
        )

    @app.route("/<string:url_addition>/aup", methods=["GET"])
    def aup_scoped(url_addition):
        if not _validate_scoped_path_or_404(url_addition):
            return ("", 404)
        return _render_legal_page(
            "Acceptable Use Policy",
            "ACCEPTABLE_USE_POLICY.md",
            endpoint_prefix=f"/{url_addition}",
        )
