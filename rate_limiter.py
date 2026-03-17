"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

from flask import session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
import os


def _read_positive_int_env(var_name, default):
    """Read positive integer from environment, falling back to default."""
    raw = os.environ.get(var_name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default

def _get_client_identifier():
    """
    Return a stable per-client identifier for rate limiting.

    Prefer a session-derived client id so that multiple users behind
    the same proxy (e.g., Tor) are not rate-limited as a single client.
    Fall back to the remote address when no session is available.
    """
    client_id = session.get("client_id")
    if client_id:
        return client_id

    # Fallback: IP-based identifier (e.g., before session is created)
    return get_remote_address()


# Global limiter instance - configured per-app in init_limiter()
_default_limits = [
    f"{_read_positive_int_env('OPSECHAT_DEFAULT_RATE_LIMIT_PER_HOUR', 200)} per hour",
    f"{_read_positive_int_env('OPSECHAT_DEFAULT_RATE_LIMIT_PER_MINUTE', 50)} per minute",
]

limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=_default_limits,
    storage_uri=os.environ.get("OPSECHAT_RATE_LIMIT_STORAGE_URI", "memory://"),
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app."""

    @app.before_request
    def _ensure_client_id():
        """
        Ensure every client has a stable session identifier used for
        rate limiting. This avoids grouping all users behind a single
        proxy (such as a Tor hidden service) under the same limit.
        """
        if "client_id" not in session:
            # Use a cryptographically secure, URL-safe token.
            session["client_id"] = secrets.token_urlsafe(16)

    limiter.init_app(app)
    return limiter
