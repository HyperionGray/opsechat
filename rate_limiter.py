"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

from flask import session
from flask import jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets
import time

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
def _on_rate_limit_breach(request_limit):
    """
    Return JSON metadata for throttled requests.

    This gives clients a stable `retry_after` value they can use for
    backoff logic and keeps API behavior consistent across endpoints.
    """
    retry_after = 1
    reset_at = getattr(request_limit, "reset_at", None)
    if reset_at is not None:
        try:
            if hasattr(reset_at, "timestamp"):
                reset_at = reset_at.timestamp()
            retry_after = max(int(float(reset_at) - time.time()), 1)
        except (TypeError, ValueError):
            retry_after = 1

    response = jsonify({
        "error": "Rate limit exceeded",
        "error_code": "rate_limited",
        "retry_after": retry_after,
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
    on_breach=_on_rate_limit_breach,
    headers_enabled=True,
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
