"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

from typing import Optional

from flask import jsonify, session
from flask_limiter.errors import RateLimitExceeded
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets

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


def rate_limit_json_response(
    *,
    retry_after: int,
    detail: Optional[str] = None,
    endpoint: Optional[str] = None,
    limit: Optional[str] = None,
):
    """
    Build a consistent JSON response for rate limit errors.

    Includes a Retry-After header and machine-readable retry metadata
    for client-side backoff logic.
    """
    retry_after = max(int(retry_after), 1)
    payload = {
        "error": "Rate limit exceeded",
        "error_code": "rate_limit_exceeded",
        "retry_after_seconds": retry_after,
        "backoff_hint": "Retry with exponential backoff.",
    }
    if detail:
        payload["detail"] = detail
    if endpoint:
        payload["endpoint"] = endpoint
    if limit:
        payload["limit"] = limit

    response = jsonify(payload)
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


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
        # Flask-Limiter exposes retry_after in most cases; fall back safely.
        retry_after = getattr(error, "retry_after", None)
        if retry_after is None:
            retry_after = 60

        detail = getattr(error, "description", None) or "Too many requests."
        limit = str(getattr(error, "limit", "")) or None
        return rate_limit_json_response(
            retry_after=retry_after,
            detail=detail,
            limit=limit,
        )

    limiter.init_app(app)
    return limiter
