"""
Tests for configurable rate limits and structured 429 responses.
"""

import os
import sys
import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import (
    RATE_LIMITS,
    DEFAULT_RATE_LIMITS,
    _rate_limit_lock,
    _rate_limit_store,
    _parse_rate_limit_override,
    build_rate_limits_from_env,
)


def _clear_store():
    with _rate_limit_lock:
        _rate_limit_store.clear()


def test_parse_rate_limit_override_max_and_window():
    max_requests, window_seconds = _parse_rate_limit_override("12/45", 3, 60)
    assert max_requests == 12
    assert window_seconds == 45


def test_parse_rate_limit_override_max_only_uses_default_window():
    max_requests, window_seconds = _parse_rate_limit_override("9", 3, 60)
    assert max_requests == 9
    assert window_seconds == 60


def test_parse_rate_limit_override_rejects_non_positive_values():
    with pytest.raises(ValueError):
        _parse_rate_limit_override("0/60", 3, 60)
    with pytest.raises(ValueError):
        _parse_rate_limit_override("5/0", 3, 60)


def test_build_rate_limits_from_env_applies_overrides():
    env = {
        "OPSECHAT_RATE_LIMIT_CHAT_CREATE": "4/30",
        "OPSECHAT_RATE_LIMIT_CHAT_MESSAGE": "50",
    }
    limits = build_rate_limits_from_env(env)

    assert limits["chat_create"]["max_requests"] == 4
    assert limits["chat_create"]["window_seconds"] == 30
    assert limits["chat_message"]["max_requests"] == 50
    assert limits["chat_message"]["window_seconds"] == DEFAULT_RATE_LIMITS["chat_message"]["window_seconds"]
    # Unset env var keeps default
    assert limits["dm_send"] == DEFAULT_RATE_LIMITS["dm_send"]


def test_build_rate_limits_from_env_ignores_invalid_overrides():
    env = {
        "OPSECHAT_RATE_LIMIT_CHAT_CREATE": "abc",
        "OPSECHAT_RATE_LIMIT_DM_SEND": "-1/30",
    }
    limits = build_rate_limits_from_env(env)
    assert limits["chat_create"] == DEFAULT_RATE_LIMITS["chat_create"]
    assert limits["dm_send"] == DEFAULT_RATE_LIMITS["dm_send"]


def test_chat_create_429_response_includes_backoff_metadata():
    _clear_store()
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    with app.test_client() as client:
        for _ in range(RATE_LIMITS["chat_create"]["max_requests"]):
            response = client.post("/chat/create", json={})
            assert response.status_code == 200

        blocked = client.post("/chat/create", json={})
        assert blocked.status_code == 429

        payload = blocked.get_json()
        assert payload["error_code"] == "rate_limit_exceeded"
        assert payload["endpoint"] == "chat_create"
        assert payload["retry_after"] >= 1
        assert payload["limit"]["max_requests"] == RATE_LIMITS["chat_create"]["max_requests"]
        assert payload["limit"]["window_seconds"] == RATE_LIMITS["chat_create"]["window_seconds"]
        assert blocked.headers.get("Retry-After") is not None
