"""
Legal policy routes for Terms, Privacy, and AUP pages.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from flask import abort, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
LEGAL_DOCS_DIR = BASE_DIR / "docs" / "legal"

POLICIES: Dict[str, Dict[str, str]] = {
    "terms": {
        "title": "Terms of Service",
        "file": "TERMS_OF_SERVICE.md",
    },
    "privacy": {
        "title": "Privacy Policy",
        "file": "PRIVACY_POLICY.md",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "file": "ACCEPTABLE_USE_POLICY.md",
    },
}


def _policy_links(url_addition: Optional[str] = None) -> list:
    prefix = f"/{url_addition}" if url_addition else ""
    return [
        {"slug": "terms", "label": "Terms", "href": f"{prefix}/terms"},
        {"slug": "privacy", "label": "Privacy", "href": f"{prefix}/privacy"},
        {"slug": "aup", "label": "AUP", "href": f"{prefix}/aup"},
    ]


def _read_policy(slug: str) -> str:
    policy = POLICIES.get(slug)
    if not policy:
        raise FileNotFoundError(f"Unknown policy slug: {slug}")

    policy_path = LEGAL_DOCS_DIR / policy["file"]
    return policy_path.read_text(encoding="utf-8")


def _extract_metadata(markdown: str) -> Dict[str, str]:
    metadata = {
        "effective_date": "Not set",
        "last_updated": "Not set",
        "version": "Not set",
    }

    patterns = {
        "effective_date": r"\*\*Effective Date:\*\*\s*(.+)",
        "last_updated": r"\*\*Last Updated:\*\*\s*(.+)",
        "version": r"\*\*Version:\*\*\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, markdown)
        if match:
            metadata[key] = match.group(1).strip()

    return metadata


def _render_policy(slug: str, url_addition: Optional[str] = None):
    policy = POLICIES.get(slug)
    if not policy:
        abort(404)

    try:
        markdown = _read_policy(slug)
    except FileNotFoundError:
        abort(404)

    metadata = _extract_metadata(markdown)
    return render_template(
        "legal_policy.html",
        title=policy["title"],
        slug=slug,
        markdown=markdown,
        links=_policy_links(url_addition),
        effective_date=metadata["effective_date"],
        last_updated=metadata["last_updated"],
        version=metadata["version"],
    )


def _policies_json(url_addition: Optional[str] = None):
    payload = {}
    links = {entry["slug"]: entry["href"] for entry in _policy_links(url_addition)}
    for slug in POLICIES:
        markdown = _read_policy(slug)
        metadata = _extract_metadata(markdown)
        payload[slug] = {
            "title": POLICIES[slug]["title"],
            "url": links[slug],
            "effective_date": metadata["effective_date"],
            "last_updated": metadata["last_updated"],
            "version": metadata["version"],
        }
    return jsonify({"policies": payload})


def register_legal_routes(app):
    """Register legal policy routes."""

    @app.route("/terms", methods=["GET"])
    def terms_page():
        return _render_policy("terms")

    @app.route("/privacy", methods=["GET"])
    def privacy_page():
        return _render_policy("privacy")

    @app.route("/aup", methods=["GET"])
    def aup_page():
        return _render_policy("aup")

    @app.route("/legal/policies.json", methods=["GET"])
    def policies_json():
        return _policies_json()

    @app.route("/<string:url_addition>/terms", methods=["GET"])
    def terms_page_prefixed(url_addition):
        return _render_policy("terms", url_addition=url_addition)

    @app.route("/<string:url_addition>/privacy", methods=["GET"])
    def privacy_page_prefixed(url_addition):
        return _render_policy("privacy", url_addition=url_addition)

    @app.route("/<string:url_addition>/aup", methods=["GET"])
    def aup_page_prefixed(url_addition):
        return _render_policy("aup", url_addition=url_addition)

    @app.route("/<string:url_addition>/legal/policies.json", methods=["GET"])
    def policies_json_prefixed(url_addition):
        return _policies_json(url_addition=url_addition)
