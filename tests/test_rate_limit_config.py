"""
Unit tests for environment-driven rate-limit configuration.
"""

from simple_chat_routes import load_rate_limits


def test_load_rate_limits_uses_defaults_for_empty_env():
    config = load_rate_limits(env={})
    assert config["chat_create"]["max_requests"] == 3
    assert config["chat_create"]["per_hour"] == 10
    assert config["chat_message"]["max_requests"] == 30
    assert config["chat_message"]["per_hour"] is None
    assert config["dm_send"]["max_requests"] == 5
    assert config["dm_send"]["per_hour"] == 20


def test_load_rate_limits_reads_environment_overrides():
    config = load_rate_limits(env={
        "OPSECHAT_CHAT_CREATE_PER_MINUTE": "8",
        "OPSECHAT_CHAT_CREATE_PER_HOUR": "40",
        "OPSECHAT_CHAT_MESSAGE_PER_MINUTE": "60",
        "OPSECHAT_CHAT_MESSAGE_PER_HOUR": "600",
        "OPSECHAT_DM_SEND_PER_MINUTE": "11",
        "OPSECHAT_DM_SEND_PER_HOUR": "90",
    })
    assert config["chat_create"]["max_requests"] == 8
    assert config["chat_create"]["per_hour"] == 40
    assert config["chat_message"]["max_requests"] == 60
    assert config["chat_message"]["per_hour"] == 600
    assert config["dm_send"]["max_requests"] == 11
    assert config["dm_send"]["per_hour"] == 90


def test_load_rate_limits_invalid_values_fall_back_to_defaults():
    config = load_rate_limits(env={
        "OPSECHAT_CHAT_CREATE_PER_MINUTE": "0",
        "OPSECHAT_CHAT_CREATE_PER_HOUR": "-1",
        "OPSECHAT_CHAT_MESSAGE_PER_MINUTE": "not-a-number",
        "OPSECHAT_DM_SEND_PER_MINUTE": "",
        "OPSECHAT_DM_SEND_PER_HOUR": "x",
    })
    assert config["chat_create"]["max_requests"] == 3
    assert config["chat_create"]["per_hour"] == 10
    assert config["chat_message"]["max_requests"] == 30
    assert config["dm_send"]["max_requests"] == 5
    assert config["dm_send"]["per_hour"] == 20
