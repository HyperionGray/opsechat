"""
Tests for environment-driven rate limit configuration.
"""

from rate_limit_config import (
    DEFAULT_CHAT_DECORATOR_LIMITS,
    DEFAULT_CHAT_ENDPOINT_LIMITS,
    DEFAULT_EMAIL_MAX_SENDS_PER_HOUR,
    DEFAULT_FLASK_DEFAULT_LIMITS,
    DEFAULT_RATE_LIMIT_STORAGE_URI,
    get_chat_decorator_limits,
    get_chat_endpoint_limits,
    get_email_max_sends_per_hour,
    get_flask_default_limits,
    get_rate_limit_storage_uri,
)


def test_rate_limit_config_defaults(monkeypatch):
    monkeypatch.delenv("OPSECHAT_EMAIL_MAX_SENDS_PER_HOUR", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_CREATE_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("OPSECHAT_DM_SEND_MAX_REQUESTS", raising=False)
    monkeypatch.delenv("OPSECHAT_DM_SEND_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_CREATE_DECORATOR_LIMIT", raising=False)
    monkeypatch.delenv("OPSECHAT_CHAT_MESSAGE_DECORATOR_LIMIT", raising=False)
    monkeypatch.delenv("OPSECHAT_DM_SEND_DECORATOR_LIMIT", raising=False)
    monkeypatch.delenv("OPSECHAT_FLASK_DEFAULT_LIMITS", raising=False)
    monkeypatch.delenv("OPSECHAT_RATE_LIMIT_STORAGE_URI", raising=False)

    assert get_email_max_sends_per_hour() == DEFAULT_EMAIL_MAX_SENDS_PER_HOUR
    assert get_chat_endpoint_limits() == DEFAULT_CHAT_ENDPOINT_LIMITS
    assert get_chat_decorator_limits() == DEFAULT_CHAT_DECORATOR_LIMITS
    assert get_flask_default_limits() == DEFAULT_FLASK_DEFAULT_LIMITS
    assert get_rate_limit_storage_uri() == DEFAULT_RATE_LIMIT_STORAGE_URI


def test_rate_limit_config_overrides(monkeypatch):
    monkeypatch.setenv("OPSECHAT_EMAIL_MAX_SENDS_PER_HOUR", "25")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", "7")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_WINDOW_SECONDS", "30")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_MAX_REQUESTS", "40")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_WINDOW_SECONDS", "90")
    monkeypatch.setenv("OPSECHAT_DM_SEND_MAX_REQUESTS", "8")
    monkeypatch.setenv("OPSECHAT_DM_SEND_WINDOW_SECONDS", "120")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_DECORATOR_LIMIT", "5 per minute")
    monkeypatch.setenv("OPSECHAT_CHAT_MESSAGE_DECORATOR_LIMIT", "100 per minute")
    monkeypatch.setenv("OPSECHAT_DM_SEND_DECORATOR_LIMIT", "10 per minute")
    monkeypatch.setenv("OPSECHAT_FLASK_DEFAULT_LIMITS", "1000 per hour; 200 per minute")
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0")

    assert get_email_max_sends_per_hour() == 25
    assert get_chat_endpoint_limits() == {
        "chat_create": {"max_requests": 7, "window_seconds": 30},
        "chat_message": {"max_requests": 40, "window_seconds": 90},
        "dm_send": {"max_requests": 8, "window_seconds": 120},
    }
    assert get_chat_decorator_limits() == {
        "chat_create": "5 per minute",
        "chat_message": "100 per minute",
        "dm_send": "10 per minute",
    }
    assert get_flask_default_limits() == ["1000 per hour", "200 per minute"]
    assert get_rate_limit_storage_uri() == "redis://localhost:6379/0"


def test_rate_limit_config_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("OPSECHAT_EMAIL_MAX_SENDS_PER_HOUR", "-1")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_MAX_REQUESTS", "abc")
    monkeypatch.setenv("OPSECHAT_CHAT_CREATE_WINDOW_SECONDS", "0")
    monkeypatch.setenv("OPSECHAT_FLASK_DEFAULT_LIMITS", "   ")
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_STORAGE_URI", "   ")

    chat_limits = get_chat_endpoint_limits()

    assert get_email_max_sends_per_hour() == DEFAULT_EMAIL_MAX_SENDS_PER_HOUR
    assert chat_limits["chat_create"] == DEFAULT_CHAT_ENDPOINT_LIMITS["chat_create"]
    assert get_flask_default_limits() == DEFAULT_FLASK_DEFAULT_LIMITS
    assert get_rate_limit_storage_uri() == DEFAULT_RATE_LIMIT_STORAGE_URI
