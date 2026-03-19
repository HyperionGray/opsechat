"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client session (falling back to client IP).
"""

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


# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=_get_client_identifier,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
)


def _safe_retry_after(value, default=60):
    """Coerce retry-after values into a positive integer number of seconds."""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = int(value)
        return max(int(value), 1)
    except (TypeError, ValueError):
        return default


def _extract_retry_after(error, default=60):
    """Best-effort extraction of Retry-After from a 429 error."""
    # Werkzeug HTTPException may expose retry_after directly.
    retry_after = getattr(error, "retry_after", None)
    if retry_after is not None:
        return _safe_retry_after(retry_after, default=default)

    # Flask-Limiter sometimes populates the response headers.
    response = getattr(error, "response", None)
    if response is None and hasattr(error, "get_response"):
        try:
            response = error.get_response()
        except Exception:
            response = None

    if response is not None:
        return _safe_retry_after(response.headers.get("Retry-After"), default=default)

    return default


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

    @app.errorhandler(429)
    def _handle_rate_limit_exceeded(error):
        """
        Return machine-readable 429 responses for chat API routes.

        This allows clients to implement reliable backoff/retry behavior using
        the same response shape whether the limit came from Flask-Limiter or
        from endpoint-specific checks.
        """
        retry_after = _extract_retry_after(error, default=60)

        if request.path.startswith("/chat/") or request.path == "/chat/create":
            response = jsonify({
                "error": "Rate limit exceeded. Please retry after the cooldown period.",
                "retry_after": retry_after,
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        if hasattr(error, "get_response"):
            return error.get_response()

        fallback = jsonify({"error": "Too many requests"})
        fallback.status_code = 429
        fallback.headers["Retry-After"] = str(retry_after)
        return fallback

    limiter.init_app(app)
    return limiter
