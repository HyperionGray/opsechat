"""
Public legal policy routes for opsechat.

These routes expose read-only legal documents at stable URLs:
- /terms
- /aup
- /privacy
"""

from pathlib import Path
from flask import render_template


_LEGAL_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "legal"


def _load_policy_markdown(filename):
    """Load a markdown policy file from docs/legal with safe fallback text."""
    policy_path = _LEGAL_DOCS_DIR / filename
    try:
        return policy_path.read_text(encoding="utf-8")
    except OSError:
        return "Policy document is temporarily unavailable. Please try again later."


def register_legal_routes(app):
    """Register public legal policy display routes."""

    @app.route("/terms", methods=["GET"])
    def terms_policy():
        return render_template(
            "legal_policy.html",
            policy_title="Terms of Service",
            policy_slug="terms",
            policy_markdown=_load_policy_markdown("TERMS_OF_SERVICE.md"),
        )

    @app.route("/aup", methods=["GET"])
    def acceptable_use_policy():
        return render_template(
            "legal_policy.html",
            policy_title="Acceptable Use Policy",
            policy_slug="aup",
            policy_markdown=_load_policy_markdown("ACCEPTABLE_USE_POLICY.md"),
        )

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        return render_template(
            "legal_policy.html",
            policy_title="Privacy Policy",
            policy_slug="privacy",
            policy_markdown=_load_policy_markdown("PRIVACY_POLICY.md"),
        )
