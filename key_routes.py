"""
Key management routes for browser-side PGP key handling.

This module serves a dedicated key management page where users can
generate, import, export, and remove keys entirely in the browser.
No private keys are uploaded to the server.
"""

import os
from flask import render_template

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _read_version():
    """Read application version from VERSION file with safe fallback."""
    try:
        with open(os.path.join(_BASE_DIR, "VERSION"), "r", encoding="utf-8") as version_file:
            return version_file.read().strip()
    except (FileNotFoundError, OSError):
        return "0.8.0-alpha"


def register_key_routes(app):
    """Register browser key-management routes."""

    @app.route("/keys", strict_slashes=False, methods=["GET"])
    def key_management():
        app_path = app.config.get("path")
        email_url = f"/{app_path}/email" if app_path else None
        return render_template(
            "key_management.html",
            version=_read_version(),
            email_url=email_url,
        )
