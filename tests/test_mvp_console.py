"""
Tests for the MVP operator console and API manifest.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _app_with_path():
    app = create_app()
    app.config["TESTING"] = True
    app.config["path"] = "secpath"
    app.config["hostname"] = "consolehost"
    app.config["full_path"] = "consolehost.onion/secpath"
    return app


def test_console_route_returns_200():
    client = _app_with_path().test_client()
    response = client.get("/console")
    assert response.status_code == 200
    assert b"Operator Console" in response.data


def test_root_redirects_to_console():
    client = _app_with_path().test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Operator Console" in response.data


def test_console_does_not_disclose_secret_path_services_by_default():
    client = _app_with_path().test_client()
    response = client.get("/console")
    body = response.data.decode()
    assert "/chat" in body
    assert "secpath" not in body
    assert "/<secret-path>/" not in body


def test_console_api_returns_service_manifest():
    client = _app_with_path().test_client()
    response = client.get("/console/api")
    assert response.status_code == 200
    data = response.get_json()
    assert data["hostname"] == "consolehost"
    assert data["profile"] == "core"
    assert data["extended_services_enabled"] is False
    assert any(service["name"] == "secure-chat" for service in data["services"])
    assert any(service["name"] == "health" for service in data["services"])
    assert not any(service["name"] == "http-mail" for service in data["services"])
    assert not any(service["name"] == "burner-receive" for service in data["services"])
