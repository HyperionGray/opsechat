"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client IP by default, with a session-aware helper
available for chat write endpoints where Tor/proxy traffic may share an IP.
"""

import hashlib

from flask import current_app, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
)


def get_session_or_ip_key():
    """Prefer a stable chat/session identity before falling back to IP."""
    session_id = session.get("_id")
    if session_id:
        return f"session:{session_id}"

    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
    session_cookie = request.cookies.get(cookie_name)
    if session_cookie:
        cookie_hash = hashlib.sha256(session_cookie.encode("utf-8")).hexdigest()
        return f"cookie:{cookie_hash}"

    return f"ip:{get_remote_address()}"


def init_limiter(app):
    """Initialize rate limiter with the Flask app"""
    limiter.init_app(app)
    return limiter
