"""
Unit tests for simple chat rate-limit configuration.
"""

from simple_chat_routes import build_rate_limit_config


def test_build_rate_limit_config_defaults():
    cfg = build_rate_limit_config({})

    assert cfg["chat_create"]["max_requests"] == 10
    assert cfg["chat_create"]["window_seconds"] == 60
    assert cfg["chat_create"]["flask_limit"] == "10 per minute"

    assert cfg["chat_message"]["max_requests"] == 30
    assert cfg["chat_message"]["window_seconds"] == 60
    assert cfg["chat_message"]["flask_limit"] == "30 per minute"

    assert cfg["dm_send"]["max_requests"] == 5
    assert cfg["dm_send"]["window_seconds"] == 60
    assert cfg["dm_send"]["flask_limit"] == "20 per hour; 5 per minute"


def test_build_rate_limit_config_env_overrides():
    cfg = build_rate_limit_config(
        {
            "OPSECHAT_CHAT_CREATE_PER_MINUTE": "7",
            "OPSECHAT_CHAT_MESSAGE_PER_MINUTE": "42",
            "OPSECHAT_DM_SEND_PER_MINUTE": "9",
            "OPSECHAT_DM_SEND_PER_HOUR": "50",
        }
    )

    assert cfg["chat_create"]["max_requests"] == 7
    assert cfg["chat_create"]["flask_limit"] == "7 per minute"

    assert cfg["chat_message"]["max_requests"] == 42
    assert cfg["chat_message"]["flask_limit"] == "42 per minute"

    assert cfg["dm_send"]["max_requests"] == 9
    assert cfg["dm_send"]["flask_limit"] == "50 per hour; 9 per minute"


def test_build_rate_limit_config_invalid_values_fallback_to_defaults():
    cfg = build_rate_limit_config(
        {
            "OPSECHAT_CHAT_CREATE_PER_MINUTE": "0",
            "OPSECHAT_CHAT_MESSAGE_PER_MINUTE": "-3",
            "OPSECHAT_DM_SEND_PER_MINUTE": "invalid",
            "OPSECHAT_DM_SEND_PER_HOUR": "",
        }
    )

    assert cfg["chat_create"]["max_requests"] == 10
    assert cfg["chat_message"]["max_requests"] == 30
    assert cfg["dm_send"]["max_requests"] == 5
    assert cfg["dm_send"]["flask_limit"] == "20 per hour; 5 per minute"
