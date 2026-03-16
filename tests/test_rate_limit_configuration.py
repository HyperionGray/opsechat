"""
Tests for environment-based simple chat rate limit configuration.
"""

from simple_chat_routes import DEFAULT_RATE_LIMITS, load_rate_limits_from_env


def test_rate_limit_defaults_when_no_env_overrides(monkeypatch):
    monkeypatch.delenv("OPSECHAT_RATE_LIMIT_CHAT_CREATE", raising=False)
    monkeypatch.delenv("OPSECHAT_RATE_LIMIT_CHAT_MESSAGE", raising=False)
    monkeypatch.delenv("OPSECHAT_RATE_LIMIT_DM_SEND", raising=False)

    limits = load_rate_limits_from_env(DEFAULT_RATE_LIMITS)
    assert limits == {
        endpoint: cfg.copy() for endpoint, cfg in DEFAULT_RATE_LIMITS.items()
    }


def test_rate_limit_valid_env_override(monkeypatch):
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_CHAT_CREATE", "12/120")

    limits = load_rate_limits_from_env(DEFAULT_RATE_LIMITS)
    assert limits["chat_create"] == {"max_requests": 12, "window_seconds": 120}
    # Unset endpoints should keep defaults
    assert limits["chat_message"] == DEFAULT_RATE_LIMITS["chat_message"]
    assert limits["dm_send"] == DEFAULT_RATE_LIMITS["dm_send"]


def test_rate_limit_invalid_override_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_CHAT_MESSAGE", "invalid")

    limits = load_rate_limits_from_env(DEFAULT_RATE_LIMITS)
    assert limits["chat_message"] == DEFAULT_RATE_LIMITS["chat_message"]


def test_rate_limit_whitespace_override_is_supported(monkeypatch):
    monkeypatch.setenv("OPSECHAT_RATE_LIMIT_DM_SEND", " 7 / 90 ")

    limits = load_rate_limits_from_env(DEFAULT_RATE_LIMITS)
    assert limits["dm_send"] == {"max_requests": 7, "window_seconds": 90}
