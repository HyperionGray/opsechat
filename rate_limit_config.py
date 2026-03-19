"""
Runtime configuration for rate limiting.

All values can be overridden with environment variables.
Invalid values fall back to safe defaults.
"""

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


DEFAULT_CHAT_ENDPOINT_LIMITS = {
    "chat_create": {"max_requests": 10, "window_seconds": 60},
    "chat_message": {"max_requests": 30, "window_seconds": 60},
    "dm_send": {"max_requests": 5, "window_seconds": 60},
}

DEFAULT_CHAT_DECORATOR_LIMITS = {
    "chat_create": "10 per hour; 3 per minute",
    "chat_message": "60 per minute",
    "dm_send": "20 per hour; 5 per minute",
}

DEFAULT_FLASK_DEFAULT_LIMITS = ["200 per hour", "50 per minute"]
DEFAULT_RATE_LIMIT_STORAGE_URI = "memory://"
DEFAULT_EMAIL_MAX_SENDS_PER_HOUR = 10


def _parse_positive_int(raw_value: str, default: int, env_name: str) -> int:
    """Parse a positive integer from env value."""
    value = (raw_value or "").strip()
    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", env_name, raw_value, default)
        return default

    if parsed <= 0:
        logger.warning("%s must be > 0 (got %s); using default %s", env_name, parsed, default)
        return default

    return parsed


def _parse_limit_list(raw_value: str, default: List[str], env_name: str) -> List[str]:
    """
    Parse a list of Flask-Limiter expressions.

    Accepts comma/semicolon-separated values, e.g.
    "500 per hour, 100 per minute" or "500 per hour; 100 per minute".
    """
    value = (raw_value or "").strip()
    if not value:
        return list(default)

    normalized = value.replace(";", ",")
    parsed = [item.strip() for item in normalized.split(",") if item.strip()]
    if not parsed:
        logger.warning("Invalid %s=%r; using defaults", env_name, raw_value)
        return list(default)

    return parsed


def get_email_max_sends_per_hour() -> int:
    """Return configured max emails sent per hour per user."""
    return _parse_positive_int(
        os.getenv("OPSECHAT_EMAIL_MAX_SENDS_PER_HOUR", ""),
        DEFAULT_EMAIL_MAX_SENDS_PER_HOUR,
        "OPSECHAT_EMAIL_MAX_SENDS_PER_HOUR",
    )


def get_chat_endpoint_limits() -> Dict[str, Dict[str, int]]:
    """Return configured in-app chat limits used by simple chat routes."""
    return {
        "chat_create": {
            "max_requests": _parse_positive_int(
                os.getenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["chat_create"]["max_requests"],
                "OPSECHAT_CHAT_CREATE_MAX_REQUESTS",
            ),
            "window_seconds": _parse_positive_int(
                os.getenv("OPSECHAT_CHAT_CREATE_WINDOW_SECONDS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["chat_create"]["window_seconds"],
                "OPSECHAT_CHAT_CREATE_WINDOW_SECONDS",
            ),
        },
        "chat_message": {
            "max_requests": _parse_positive_int(
                os.getenv("OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["chat_message"]["max_requests"],
                "OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS",
            ),
            "window_seconds": _parse_positive_int(
                os.getenv("OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["chat_message"]["window_seconds"],
                "OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS",
            ),
        },
        "dm_send": {
            "max_requests": _parse_positive_int(
                os.getenv("OPSECHAT_DM_SEND_MAX_REQUESTS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["dm_send"]["max_requests"],
                "OPSECHAT_DM_SEND_MAX_REQUESTS",
            ),
            "window_seconds": _parse_positive_int(
                os.getenv("OPSECHAT_DM_SEND_WINDOW_SECONDS", ""),
                DEFAULT_CHAT_ENDPOINT_LIMITS["dm_send"]["window_seconds"],
                "OPSECHAT_DM_SEND_WINDOW_SECONDS",
            ),
        },
    }


def get_chat_decorator_limits() -> Dict[str, str]:
    """Return Flask-Limiter decorator strings for chat routes."""
    configured = {}
    env_map = {
        "chat_create": "OPSECHAT_CHAT_CREATE_DECORATOR_LIMIT",
        "chat_message": "OPSECHAT_CHAT_MESSAGE_DECORATOR_LIMIT",
        "dm_send": "OPSECHAT_DM_SEND_DECORATOR_LIMIT",
    }

    for key, env_name in env_map.items():
        raw_value = (os.getenv(env_name, "") or "").strip()
        configured[key] = raw_value or DEFAULT_CHAT_DECORATOR_LIMITS[key]

    return configured


def get_flask_default_limits() -> List[str]:
    """Return default app-wide Flask-Limiter limits."""
    return _parse_limit_list(
        os.getenv("OPSECHAT_FLASK_DEFAULT_LIMITS", ""),
        DEFAULT_FLASK_DEFAULT_LIMITS,
        "OPSECHAT_FLASK_DEFAULT_LIMITS",
    )


def get_rate_limit_storage_uri() -> str:
    """Return Flask-Limiter backend URI."""
    value = (os.getenv("OPSECHAT_RATE_LIMIT_STORAGE_URI", "") or "").strip()
    return value or DEFAULT_RATE_LIMIT_STORAGE_URI
