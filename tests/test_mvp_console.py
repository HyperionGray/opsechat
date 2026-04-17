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


def test_console_links_secret_path_services():
    client = _app_with_path().test_client()
    response = client.get("/console")
    body = response.data.decode()
    assert "/secpath/mail" in body
    assert "/secpath/email/burner" in body
    assert "/chat" in body


def test_console_api_returns_service_manifest():
    client = _app_with_path().test_client()
    response = client.get("/console/api")
    assert response.status_code == 200
    data = response.get_json()
    assert data["secret_path"] == "secpath"
    assert data["hostname"] == "consolehost"
    assert any(service["name"] == "secure-chat" for service in data["services"])
    assert any(service["name"] == "http-mail" for service in data["services"])
