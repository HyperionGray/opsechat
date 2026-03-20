"""
Legal policy routes for opsechat.

Provides simple read-only policy pages backed by markdown files in docs/legal.
"""

from pathlib import Path
from flask import abort, render_template


POLICY_CONFIG = {
    "terms": {
        "title": "Terms of Service",
        "path": "docs/legal/TERMS_OF_SERVICE.md",
        "slug": "terms",
    },
    "privacy": {
        "title": "Privacy Policy",
        "path": "docs/legal/PRIVACY_POLICY.md",
        "slug": "privacy",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "path": "docs/legal/ACCEPTABLE_USE_POLICY.md",
        "slug": "aup",
    },
}


def _load_policy_text(relative_path: str) -> str:
    """Load a policy markdown file from repository root."""
    repo_root = Path(__file__).resolve().parent
    policy_path = repo_root / relative_path
    try:
        return policy_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _render_policy(policy_key: str):
    config = POLICY_CONFIG[policy_key]
    content = _load_policy_text(config["path"])
    if not content:
        abort(404)
    return render_template(
        "legal_policy.html",
        title=config["title"],
        content=content,
        active_slug=config["slug"],
    )


def register_legal_routes(app):
    """Register legal policy endpoints."""

    @app.route("/terms", methods=["GET"])
    def terms_page():
        return _render_policy("terms")

    @app.route("/privacy", methods=["GET"])
    def privacy_page():
        return _render_policy("privacy")

    @app.route("/aup", methods=["GET"])
    def aup_page():
        return _render_policy("aup")
