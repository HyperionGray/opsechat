"""
Key management routes for OpSecChat.

Provides a browser-side key management UI at /keys.
Private keys remain client-side (localStorage) and are never posted to server.
"""

from flask import render_template


def _read_version() -> str:
    """Read app version from VERSION file with safe fallback."""
    try:
        with open("VERSION", "r", encoding="utf-8") as version_file:
            return version_file.read().strip()
    except OSError:
        return "0.8.0-alpha"


def register_key_routes(app):
    """Register key management routes."""

    @app.route("/keys", methods=["GET"])
    def key_management():
        """Render browser-side PGP key management page."""
        return render_template("key_management.html", version=_read_version())
