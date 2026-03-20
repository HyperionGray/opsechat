"""
Key management routes.

Provides a browser-only key management page for generating, importing,
exporting, and deleting AES-GCM keys without server-side persistence.
"""

from flask import render_template


def _read_version(default: str = "0.8.0-alpha") -> str:
    """Read semantic version from VERSION file with a safe fallback."""
    try:
        with open("VERSION", "r", encoding="utf-8") as version_file:
            value = version_file.read().strip()
            return value or default
    except OSError:
        return default


def register_key_routes(app):
    """Register key management routes with the Flask app."""

    @app.route("/keys", methods=["GET"])
    def key_management():
        return render_template("key_management.html", version=_read_version())
