"""
Legal policy routes for OpSecChat.

Serves policy documents from docs/legal as read-only pages:
- /terms
- /privacy
- /aup
"""

from functools import lru_cache
from pathlib import Path

from flask import abort, render_template


LEGAL_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "legal"

POLICY_CONFIG = {
    "terms": ("TERMS_OF_SERVICE.md", "Terms of Service"),
    "privacy": ("PRIVACY_POLICY.md", "Privacy Policy"),
    "aup": ("ACCEPTABLE_USE_POLICY.md", "Acceptable Use Policy"),
}


@lru_cache(maxsize=8)
def _read_policy_text(filename: str) -> str:
    """Read and cache legal policy markdown content from disk."""
    policy_path = LEGAL_DOCS_DIR / filename
    return policy_path.read_text(encoding="utf-8")


def _render_policy(slug: str):
    """Render a policy page from docs/legal."""
    filename, title = POLICY_CONFIG[slug]
    try:
        policy_text = _read_policy_text(filename)
    except OSError:
        abort(503, description=f"{title} is temporarily unavailable")

    return render_template(
        "legal_policy.html",
        policy_title=title,
        policy_text=policy_text,
    )


def register_legal_routes(app):
    """Register legal policy display routes with the Flask app."""

    @app.route("/terms", methods=["GET"])
    def terms_policy():
        return _render_policy("terms")

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        return _render_policy("privacy")

    @app.route("/aup", methods=["GET"])
    def aup_policy():
        return _render_policy("aup")
