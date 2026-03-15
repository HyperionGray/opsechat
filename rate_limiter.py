"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client IP (or session where applicable).
"""

import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


DEFAULT_LIMITS = ["200 per hour", "50 per minute"]


def _parse_default_limits(value):
    """Parse env config into a Flask-Limiter compatible list."""
    if not value:
        return DEFAULT_LIMITS
    normalized = value.replace(";", ",")
    parsed = [part.strip() for part in normalized.split(",") if part.strip()]
    return parsed or DEFAULT_LIMITS


# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=DEFAULT_LIMITS,
    storage_uri="memory://",
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app"""
    app.config.setdefault(
        "RATELIMIT_DEFAULT",
        _parse_default_limits(os.getenv("OPSECHAT_RATELIMIT_DEFAULT")),
    )
    app.config.setdefault(
        "RATELIMIT_STORAGE_URI",
        os.getenv("OPSECHAT_RATELIMIT_STORAGE_URI", "memory://"),
    )
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)
    return limiter
