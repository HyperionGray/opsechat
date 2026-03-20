"""
Key management routes.

Provides a browser-based page for local PGP key management.
All key operations happen client-side in the browser.
"""

from flask import render_template


def register_key_routes(app):
    """Register key management routes."""

    @app.route("/keys", methods=["GET"])
    def key_management():
        """Render browser-side key management UI."""
        return render_template("key_management.html")
