"""
Tests for /version operational endpoint.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stub_route_modules():
    """Provide lightweight route modules so create_app can initialize in isolation."""
    simple_chat_routes = types.ModuleType("simple_chat_routes")
    simple_chat_routes.register_simple_chat_routes = lambda app: None
    sys.modules["simple_chat_routes"] = simple_chat_routes

    chat_routes = types.ModuleType("chat_routes")
    chat_routes.register_chat_routes = lambda *args, **kwargs: None
    sys.modules["chat_routes"] = chat_routes

    review_routes = types.ModuleType("review_routes")
    review_routes.register_review_routes = lambda *args, **kwargs: None
    sys.modules["review_routes"] = review_routes


def test_version_endpoint_returns_version_from_file():
    _stub_route_modules()

    from app_factory import create_app
    from monitoring import get_version

    app = create_app()
    client = app.test_client()
    response = client.get("/version")
    version = get_version()

    assert response.status_code == 200
    assert isinstance(version, str)
    assert version.strip() != ""
    payload = response.get_json()
    # Stable monitoring payload: service, version, and a timestamp the operator
    # can use to detect a stalled process.
    assert payload["service"] == "opsechat"
    assert payload["version"] == version
    assert isinstance(payload["timestamp"], str) and payload["timestamp"]


def test_version_endpoint_includes_security_headers():
    _stub_route_modules()

    from app_factory import create_app

    app = create_app()
    client = app.test_client()
    response = client.get("/version")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, dict)
    assert "version" in data
    assert isinstance(data["version"], str)
    assert data["version"]
    assert response.content_type == "application/json"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"

def test_console_manifest_lists_version_endpoint():
    _stub_route_modules()

    from app_factory import create_app

    app = create_app()
    client = app.test_client()
    response = client.get("/console/api")
    payload = response.get_json()

    health_service = next(service for service in payload["services"] if service["name"] == "health")
    assert "/version" in health_service["api"]
