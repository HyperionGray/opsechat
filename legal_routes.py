"""
Legal policy routes for opsechat.

Serves human-readable policy pages and exposes policy version metadata
for Terms of Service, Acceptable Use Policy, and Privacy Policy.
"""

import os
import re
from flask import jsonify, make_response, render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LEGAL_DIR = os.path.join(_BASE_DIR, "docs", "legal")

_POLICY_CONFIG = {
    "terms": {
        "route": "/terms",
        "filename": "TERMS_OF_SERVICE.md",
        "fallback_title": "Terms of Service",
    },
    "aup": {
        "route": "/aup",
        "filename": "ACCEPTABLE_USE_POLICY.md",
        "fallback_title": "Acceptable Use Policy",
    },
    "privacy": {
        "route": "/privacy",
        "filename": "PRIVACY_POLICY.md",
        "fallback_title": "Privacy Policy",
    },
}


def _extract_metadata(markdown_text: str, fallback_title: str) -> dict:
    """Extract lightweight metadata from a markdown policy document."""
    title_match = re.search(r"^#\s+(.+)$", markdown_text, flags=re.MULTILINE)
    effective_date_match = re.search(
        r"^\*\*Effective Date:\*\*\s*(.+)$", markdown_text, flags=re.MULTILINE
    )
    last_updated_match = re.search(
        r"^\*\*Last Updated:\*\*\s*(.+)$", markdown_text, flags=re.MULTILINE
    )
    version_matches = re.findall(
        r"^\*\*Version:\*\*\s*(.+)$", markdown_text, flags=re.MULTILINE
    )

    return {
        "title": (title_match.group(1).strip() if title_match else fallback_title),
        "effective_date": (
            effective_date_match.group(1).strip()
            if effective_date_match
            else "Not specified"
        ),
        "last_updated": (
            last_updated_match.group(1).strip()
            if last_updated_match
            else "Not specified"
        ),
        "version": version_matches[-1].strip() if version_matches else "Not specified",
    }


def _load_policy(policy_key: str) -> dict:
    """Load policy content and metadata from docs/legal."""
    config = _POLICY_CONFIG[policy_key]
    source_path = os.path.join(_LEGAL_DIR, config["filename"])

    with open(source_path, "r", encoding="utf-8") as policy_file:
        content = policy_file.read()

    metadata = _extract_metadata(content, config["fallback_title"])
    metadata["content"] = content
    metadata["route"] = config["route"]
    metadata["source"] = f"docs/legal/{config['filename']}"
    return metadata


def _render_policy_page(policy_key: str):
    """Render a policy page and add explicit policy metadata headers."""
    policy = _load_policy(policy_key)
    response = make_response(render_template("legal_policy.html", policy=policy))
    response.headers["X-Policy-Version"] = policy["version"]
    response.headers["X-Policy-Last-Updated"] = policy["last_updated"]
    response.headers["X-Policy-Effective-Date"] = policy["effective_date"]
    return response


def register_legal_routes(app):
    """Register legal policy routes with the Flask application."""

    @app.route("/terms", methods=["GET"])
    def terms_of_service():
        return _render_policy_page("terms")

    @app.route("/aup", methods=["GET"])
    def acceptable_use_policy():
        return _render_policy_page("aup")

    @app.route("/privacy", methods=["GET"])
    def privacy_policy():
        return _render_policy_page("privacy")

    @app.route("/policy/versions", methods=["GET"])
    def policy_versions():
        policies = {}
        for policy_key in _POLICY_CONFIG:
            policy = _load_policy(policy_key)
            policies[policy_key] = {
                "title": policy["title"],
                "version": policy["version"],
                "effective_date": policy["effective_date"],
                "last_updated": policy["last_updated"],
                "route": policy["route"],
                "source": policy["source"],
            }
        return jsonify({"policies": policies})
