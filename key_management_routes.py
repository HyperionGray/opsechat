"""
Key management routes for browser-side PGP workflows.
"""

from flask import render_template


def register_key_management_routes(app):
    """Register key management UI routes."""

    @app.route("/keys", methods=["GET"])
    def key_management():
        return render_template("key_management.html")
