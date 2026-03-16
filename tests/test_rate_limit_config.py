"""
Tests for environment-driven chat rate limit configuration.
"""

from simple_chat_routes import (
    build_rate_limit_config,
    DEFAULT_FLASK_LIMITS,
    DEFAULT_RATE_LIMITS,
)


def test_build_rate_limit_config_uses_defaults():
    rate_limits, flask_limits = build_rate_limit_config(env={})
    assert rate_limits == DEFAULT_RATE_LIMITS
    assert flask_limits == DEFAULT_FLASK_LIMITS


def test_build_rate_limit_config_applies_valid_overrides():
    env = {
        "OPSECHAT_CHAT_CREATE_MAX_REQUESTS": "7",
        "OPSECHAT_CHAT_CREATE_WINDOW_SECONDS": "90",
        "OPSECHAT_CHAT_CREATE_FLASK_LIMIT": "15 per hour; 7 per 90 seconds",
        "OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS": "40",
        "OPSECHAT_DM_SEND_WINDOW_SECONDS": "120",
    }
    rate_limits, flask_limits = build_rate_limit_config(env=env)

    assert rate_limits["chat_create"]["max_requests"] == 7
    assert rate_limits["chat_create"]["window_seconds"] == 90
    assert flask_limits["chat_create"] == "15 per hour; 7 per 90 seconds"

    assert rate_limits["chat_message"]["max_requests"] == 40
    assert (
        rate_limits["chat_message"]["window_seconds"]
        == DEFAULT_RATE_LIMITS["chat_message"]["window_seconds"]
    )
    assert rate_limits["dm_send"]["window_seconds"] == 120


def test_build_rate_limit_config_ignores_invalid_int_overrides():
    env = {
        "OPSECHAT_CHAT_CREATE_MAX_REQUESTS": "zero",
        "OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS": "0",
        "OPSECHAT_DM_SEND_MAX_REQUESTS": "-1",
    }
    rate_limits, _ = build_rate_limit_config(env=env)

    assert rate_limits["chat_create"] == DEFAULT_RATE_LIMITS["chat_create"]
    assert rate_limits["chat_message"] == DEFAULT_RATE_LIMITS["chat_message"]
    assert rate_limits["dm_send"] == DEFAULT_RATE_LIMITS["dm_send"]
