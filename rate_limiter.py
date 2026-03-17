"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

from flask import jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
import secrets


SIMPLE_CHAT_LIMIT_POLICIES = {
    "chat_create": "10 per hour; 3 per minute",
    "chat_message_write": "60 per minute",
    "dm_send": "20 per hour; 5 per minute",
}


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
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
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

    @app.errorhandler(RateLimitExceeded)
    def _handle_rate_limit_exceeded(error):
        """Return consistent JSON metadata for client retry/backoff logic."""
        retry_after = int(getattr(error, "retry_after", 1) or 1)
        endpoint = (request.endpoint or "unknown").split(".")[-1]

        response = jsonify({
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Back off and retry later.",
            "retry_after_seconds": max(retry_after, 1),
            "endpoint": endpoint,
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(max(retry_after, 1))
        response.headers["Cache-Control"] = "no-store"
        return response

    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)
    return limiter
