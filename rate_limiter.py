"""
Rate limiting helpers for OpSecChat.

By default, limits are keyed to a stable per-session client id so users behind
the same proxy/Tor exit are not rate-limited together. If a session is not
available, we fall back to a best-effort client IP key.
"""

import secrets

from flask import has_request_context, request, session
from flask_limiter import Limiter

RATE_LIMIT_SESSION_KEY = "_rate_limit_client_id"


def ensure_rate_limit_client_id():
    """Create and persist a stable client id in session if missing."""
    if not has_request_context():
        return None

    client_id = session.get(RATE_LIMIT_SESSION_KEY)
    if not client_id:
        client_id = secrets.token_urlsafe(16)
        session[RATE_LIMIT_SESSION_KEY] = client_id
    return client_id


def get_rate_limit_key():
    """Build the key used by Flask-Limiter for request accounting."""
    if not has_request_context():
        return "global"

    client_id = session.get(RATE_LIMIT_SESSION_KEY)
    if client_id:
        return f"session:{client_id}"

    # Fall back to source IP if session state is unavailable.
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    source_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr
    return f"ip:{source_ip or 'unknown'}"


# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app."""
    limiter.init_app(app)
    return limiter
