"""
Rate limit configuration helpers.

Supports environment-driven tuning for simple chat endpoint limits while
keeping safe defaults for local development and CI.
"""

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional


DEFAULT_SIMPLE_CHAT_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "chat_create": {"max_requests": 10, "window_seconds": 60},
    "chat_message": {"max_requests": 30, "window_seconds": 60},
    "dm_send": {"max_requests": 5, "window_seconds": 60},
}

DEFAULT_FLASK_LIMIT_STRINGS: Dict[str, str] = {
    "chat_create": "10 per hour; 3 per minute",
    "chat_message": "60 per minute",
    "dm_send": "20 per hour; 5 per minute",
}

_ENV_SIMPLE_LIMIT_MAP = {
    "chat_create": (
        "OPSECHAT_LIMIT_CHAT_CREATE_MAX_REQUESTS",
        "OPSECHAT_LIMIT_CHAT_CREATE_WINDOW_SECONDS",
    ),
    "chat_message": (
        "OPSECHAT_LIMIT_CHAT_MESSAGE_MAX_REQUESTS",
        "OPSECHAT_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS",
    ),
    "dm_send": (
        "OPSECHAT_LIMIT_DM_SEND_MAX_REQUESTS",
        "OPSECHAT_LIMIT_DM_SEND_WINDOW_SECONDS",
    ),
}

_ENV_FLASK_LIMIT_MAP = {
    "chat_create": "OPSECHAT_LIMIT_CHAT_CREATE_DECORATOR",
    "chat_message": "OPSECHAT_LIMIT_CHAT_MESSAGE_DECORATOR",
    "dm_send": "OPSECHAT_LIMIT_DM_SEND_DECORATOR",
}


def _parse_positive_int(raw_value: Optional[str], default_value: int) -> int:
    """Parse positive integer env values with safe fallback."""
    if raw_value is None:
        return default_value

    try:
        parsed = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default_value

    if parsed <= 0:
        return default_value
    return parsed


def load_rate_limit_settings(
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build effective rate limit settings from defaults + environment variables.

    Returns dict with:
      - simple_limits: endpoint -> {max_requests, window_seconds}
      - flask_limits: endpoint -> flask-limiter string
    """
    if env is None:
        import os

        env = os.environ

    simple_limits = deepcopy(DEFAULT_SIMPLE_CHAT_RATE_LIMITS)
    flask_limits = deepcopy(DEFAULT_FLASK_LIMIT_STRINGS)

    for endpoint, (max_env, window_env) in _ENV_SIMPLE_LIMIT_MAP.items():
        defaults = DEFAULT_SIMPLE_CHAT_RATE_LIMITS[endpoint]
        simple_limits[endpoint]["max_requests"] = _parse_positive_int(
            env.get(max_env), defaults["max_requests"]
        )
        simple_limits[endpoint]["window_seconds"] = _parse_positive_int(
            env.get(window_env), defaults["window_seconds"]
        )

    for endpoint, env_name in _ENV_FLASK_LIMIT_MAP.items():
        raw_value = env.get(env_name)
        if raw_value is None:
            continue
        normalized = str(raw_value).strip()
        if normalized:
            flask_limits[endpoint] = normalized

    return {
        "simple_limits": simple_limits,
        "flask_limits": flask_limits,
    }
