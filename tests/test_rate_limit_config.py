"""
Tests for environment-driven rate limit configuration.
"""

from simple_chat_routes import load_rate_limit_config


def test_load_rate_limit_config_uses_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("OPSECHAT_CHAT_CREATE_PER_MINUTE", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_CREATE_PER_HOUR", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_MESSAGE_PER_MINUTE", raising=False)
    monkeypatch.delenv("OPSECHAT_DM_SEND_PER_MINUTE", raising=False)
    monkeypatch.delenv("OPSECHAT_DM_SEND_PER_HOUR", raising=False)

    config = load_rate_limit_config()

    assert config["chat_create_per_minute"] == 3
    assert config["chat_create_per_hour"] == 10
    assert config["chat_message_per_minute"] == 30
    assert config["dm_send_per_minute"] == 5
    assert config["dm_send_per_hour"] == 20
    assert config["flask_limit_chat_create"] == "10 per hour; 3 per minute"
    assert config["flask_limit_chat_message_post"] == "30 per minute"
    assert config["flask_limit_dm_send"] == "20 per hour; 5 per minute"


def test_load_rate_limit_config_reads_valid_env_overrides(monkeypatch):
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_PER_MINUTE", "7")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_PER_HOUR", "50")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_PER_MINUTE", "44")
    monkeypatch.setenv("OPSECHAT_DM_SEND_PER_MINUTE", "9")
    monkeypatch.setenv("OPSECHAT_DM_SEND_PER_HOUR", "30")

    config = load_rate_limit_config()

    assert config["chat_create_per_minute"] == 7
    assert config["chat_create_per_hour"] == 50
    assert config["chat_message_per_minute"] == 44
    assert config["dm_send_per_minute"] == 9
    assert config["dm_send_per_hour"] == 30
    assert config["flask_limit_chat_create"] == "50 per hour; 7 per minute"
    assert config["flask_limit_chat_message_post"] == "44 per minute"
    assert config["flask_limit_dm_send"] == "30 per hour; 9 per minute"


def test_load_rate_limit_config_falls_back_on_invalid_env_values(monkeypatch):
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_PER_MINUTE", "0")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_PER_HOUR", "-1")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_PER_MINUTE", "abc")
    monkeypatch.setenv("OPSECHAT_DM_SEND_PER_MINUTE", "")
    monkeypatch.setenv("OPSECHAT_DM_SEND_PER_HOUR", "   ")

    config = load_rate_limit_config()

    assert config["chat_create_per_minute"] == 3
    assert config["chat_create_per_hour"] == 10
    assert config["chat_message_per_minute"] == 30
    assert config["dm_send_per_minute"] == 5
    assert config["dm_send_per_hour"] == 20
