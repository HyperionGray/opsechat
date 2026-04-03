"""
Browser-side key management routes for opsechat.

Keys are generated/imported/exported in the user's browser and are never
stored server-side.
"""

import os
from flask import render_template

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _read_version():
    """Read project version from VERSION file."""
    try:
        with open(os.path.join(_BASE_DIR, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, FileNotFoundError):
        return "0.8.0-alpha"


def register_keys_routes(app):
    """Register key management routes."""

    @app.route("/keys", methods=["GET"])
    def keys_page():
        return render_template("keys.html", version=_read_version())
