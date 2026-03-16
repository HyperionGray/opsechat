"""
Tests for environment-driven rate limit configuration.
"""

from app_factory import create_app
from rate_limit_config import (
    DEFAULT_FLASK_LIMIT_STRINGS,
    DEFAULT_SIMPLE_CHAT_RATE_LIMITS,
    load_rate_limit_settings,
)
from simple_chat_routes import _rate_limit_lock, _rate_limit_store


def _clear_rate_limit_store():
    with _rate_limit_lock:
        _rate_limit_store.clear()


def test_rate_limit_settings_defaults():
    settings = load_rate_limit_settings(env={})
    assert settings["simple_limits"] == DEFAULT_SIMPLE_CHAT_RATE_LIMITS
    assert settings["flask_limits"] == DEFAULT_FLASK_LIMIT_STRINGS


def test_rate_limit_settings_env_overrides_and_invalid_fallback():
    settings = load_rate_limit_settings(
        env={
            "OPSECHAT_LIMIT_CHAT_MESSAGE_MAX_REQUESTS": "42",
            "OPSECHAT_LIMIT_CHAT_MESSAGE_WINDOW_SECONDS": "120",
            "OPSECHAT_LIMIT_DM_SEND_MAX_REQUESTS": "-5",  # invalid
            "OPSECHAT_LIMIT_DM_SEND_WINDOW_SECONDS": "abc",  # invalid
            "OPSECHAT_LIMIT_CHAT_CREATE_DECORATOR": "7 per minute",
        }
    )

    assert settings["simple_limits"]["chat_message"] == {
        "max_requests": 42,
        "window_seconds": 120,
    }

    # Invalid values should fall back to defaults.
    assert settings["simple_limits"]["dm_send"] == DEFAULT_SIMPLE_CHAT_RATE_LIMITS[
        "dm_send"
    ]
    assert settings["flask_limits"]["chat_create"] == "7 per minute"


def test_dm_rate_limit_can_be_configured_from_env(monkeypatch):
    monkeypatch.setenv("OPSECHAT_LIMIT_DM_SEND_MAX_REQUESTS", "1")
    monkeypatch.setenv("OPSECHAT_LIMIT_DM_SEND_WINDOW_SECONDS", "60")

    _clear_rate_limit_store()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        payload = {"room_id": "room-a", "message": "hello"}
        first = client.post("/chat/dm/send", json=payload)
        second = client.post("/chat/dm/send", json=payload)

        assert first.status_code == 200
        assert second.status_code == 429
        assert "Maximum 1 DMs per 60 seconds" in second.get_json()["error"]


def test_flask_limiter_string_can_be_configured_from_env(monkeypatch):
    monkeypatch.setenv("OPSECHAT_LIMIT_CHAT_CREATE_DECORATOR", "1 per minute")

    _clear_rate_limit_store()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        first = client.post("/chat/create", content_type="application/json")
        second = client.post("/chat/create", content_type="application/json")

        assert first.status_code == 200
        assert second.status_code == 429
