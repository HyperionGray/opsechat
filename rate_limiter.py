"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

import time
from flask import jsonify, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import secrets


def build_rate_limit_response(
    retry_after_seconds,
    *,
    message="Rate limit exceeded. Please try again later.",
    limit=None,
    endpoint=None,
):
    """
    Build a consistent JSON 429 response with backoff metadata.
    """
    retry_after = max(int(retry_after_seconds or 0), 1)
    payload = {
        "error": message,
        "code": "rate_limited",
        "retry_after_seconds": retry_after,
        "backoff": {
            "strategy": "fixed-window",
            "retry_after_seconds": retry_after,
        },
    }
    if limit:
        payload["limit"] = str(limit)
    if endpoint:
        payload["endpoint"] = endpoint

    response = jsonify(payload)
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-RateLimit-Retry-After"] = str(retry_after)
    return response


def _extract_retry_after_seconds(request_limit):
    """
    Best-effort extraction of retry-after value from Flask-Limiter metadata.
    """
    reset_at = getattr(request_limit, "reset_at", None)
    if reset_at is None:
        return 1

    try:
        if hasattr(reset_at, "timestamp"):
            return max(int(reset_at.timestamp() - time.time()), 1)
        return max(int(float(reset_at) - time.time()), 1)
    except (TypeError, ValueError, OSError):
        return 1


def _on_rate_limit_breach(request_limit):
    """
    Return JSON for Flask-Limiter breaches (instead of default HTML).
    """
    endpoint = getattr(request, "endpoint", None)
    retry_after = _extract_retry_after_seconds(request_limit)
    return build_rate_limit_response(
        retry_after,
        message="Rate limit exceeded for this endpoint.",
        limit=getattr(request_limit, "limit", None),
        endpoint=endpoint,
    )


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
    on_breach=_on_rate_limit_breach,
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app."""
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)

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
