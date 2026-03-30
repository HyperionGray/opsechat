"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

import datetime
import time
import math
from flask import session, request, jsonify
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


def _compute_retry_after_seconds(request_limit):
    """
    Return an integer Retry-After value for Flask-Limiter breaches.
    """
    reset_at = getattr(request_limit, "reset_at", None)
    if reset_at is None:
        return 1

    if isinstance(reset_at, datetime.datetime):
        # Normalize to UTC-aware datetimes to avoid naive/aware subtraction errors.
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=datetime.timezone.utc)
        delta = (reset_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    else:
        try:
            delta = float(reset_at) - time.time()
        except (TypeError, ValueError):
            delta = 1

    return max(math.ceil(delta), 1)


def _build_rate_limiter_breach_response(request_limit):
    """
    Build a consistent JSON payload for Flask-Limiter 429 responses.
    """
    retry_after = _compute_retry_after_seconds(request_limit)
    retry_at = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=retry_after)
    ).isoformat()

    limit_obj = getattr(request_limit, "limit", None)
    max_requests = getattr(limit_obj, "amount", None)
    window_seconds = None
    get_expiry = getattr(limit_obj, "get_expiry", None)
    if callable(get_expiry):
        try:
            window_seconds = int(get_expiry())
        except (TypeError, ValueError):
            window_seconds = None

    endpoint = request.endpoint or request.path
    payload = {
        "error": f"Rate limit exceeded. Try again in {retry_after} seconds.",
        "error_code": "RATE_LIMIT_EXCEEDED",
        "endpoint": endpoint,
        "retry_after": retry_after,
        "retry_at": retry_at,
        "backoff": {
            "strategy": "fixed",
            "retry_after_seconds": retry_after,
        },
        "limit": {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
        },
    }
    response = jsonify(payload)
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-RateLimit-Retry-After"] = str(retry_after)
    return response


# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
    on_breach=_build_rate_limiter_breach_response,
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app."""
    # We set Retry-After headers ourselves on 429 payloads.
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", False)

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
