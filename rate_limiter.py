"""
Rate Limiter for OpSecChat

Configures Flask-Limiter to protect API endpoints from abuse.
Limits are applied per client IP (or session where applicable).
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance - configured per-app in init_limiter()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://",
)


def init_limiter(app):
    """Initialize rate limiter with the Flask app"""
    limiter.init_app(app)
    return limiter
