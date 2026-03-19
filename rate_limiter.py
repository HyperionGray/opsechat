"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

from flask import session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
from rate_limit_config import get_flask_default_limits, get_rate_limit_storage_uri

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
limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=get_flask_default_limits(),
    storage_uri=get_rate_limit_storage_uri(),
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
