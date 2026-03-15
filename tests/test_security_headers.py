"""
Tests for default security headers configured in app_factory.create_app.
"""

from app_factory import create_app


def test_default_security_headers_present():
    app = create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("Server") == "OpSecChat"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("Permissions-Policy") is not None
    assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, private, max-age=0"
    assert response.headers.get("Content-Security-Policy") is not None
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_csp_can_be_overridden_with_environment_variable(monkeypatch):
    custom_policy = "default-src 'none'; frame-ancestors 'none';"
    monkeypatch.setenv("OPSECHAT_CSP", custom_policy)
    monkeypatch.delenv("OPSECHAT_DISABLE_CSP", raising=False)

    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("Content-Security-Policy") == custom_policy


def test_csp_can_be_disabled_with_environment_variable(monkeypatch):
    monkeypatch.setenv("OPSECHAT_DISABLE_CSP", "true")
    monkeypatch.delenv("OPSECHAT_CSP", raising=False)

    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
