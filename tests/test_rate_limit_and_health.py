"""
Integration tests for simple-chat rate-limiting and /health endpoint behavior.
"""

import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _make_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _exhaust_chat_create_limit(client):
    for _ in range(3):
        r = client.post("/chat/create", content_type="application/json")
        assert r.status_code == 200
    return client.post("/chat/create", content_type="application/json")


def test_rate_limit_429_includes_retry_headers_and_metadata():
    app = _make_app()
    with app.test_client() as client:
        limited = _exhaust_chat_create_limit(client)
        assert limited.status_code == 429

        payload = limited.get_json()
        assert payload is not None
        assert payload.get("error") == "rate_limit_exceeded"
        assert payload.get("retry_after_seconds", 0) >= 1
        assert payload.get("endpoint") == "chat_create"

        retry_after_header = limited.headers.get("Retry-After")
        assert retry_after_header is not None
        assert int(retry_after_header) >= 1


def test_rate_limit_isolation_between_sessions():
    app = _make_app()
    with app.test_client() as client_a:
        limited = _exhaust_chat_create_limit(client_a)
        assert limited.status_code == 429

    with app.test_client() as client_b:
        fresh = client_b.post("/chat/create", content_type="application/json")
        assert fresh.status_code == 200


def test_chat_limits_endpoint_returns_policies():
    app = _make_app()
    with app.test_client() as client:
        response = client.get("/chat/limits")
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert data.get("chat_create") == "10 per hour; 3 per minute"
        assert data.get("chat_message_write") == "60 per minute"
        assert data.get("dm_send") == "20 per hour; 5 per minute"
        assert "retry_hint" in data


def test_health_endpoint_returns_200():
    app = _make_app()
    with app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200


def test_health_endpoint_returns_expected_fields():
    app = _make_app()
    with app.test_client() as client:
        response = client.get("/health")
        data = response.get_json()
        assert data is not None
        assert data.get("status") == "healthy"
        assert "version" in data
        assert "checks" in data
        assert isinstance(data.get("checks"), dict)
        assert isinstance(data.get("uptime_seconds"), (int, float))
