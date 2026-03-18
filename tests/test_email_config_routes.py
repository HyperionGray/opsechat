"""
Integration tests for email configuration and domain rotation routes.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _make_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["path"] = "test-path"
    app.config["hostname"] = "localhost"
    return app.test_client()


def _init_session(client):
    # Any page hit initializes session in the route handlers.
    response = client.get("/test-path/email/config")
    assert response.status_code == 200


def test_email_config_page_renders_with_runtime_status():
    client = _make_client()
    response = client.get("/test-path/email/config")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Email System Configuration" in body
    assert "Budget Status" in body


@patch("email_routes.domain_rotation_manager.configure")
def test_email_config_post_domain_settings_calls_manager(mock_configure):
    client = _make_client()
    _init_session(client)

    response = client.post(
        "/test-path/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk_test_1234",
            "api_secret": "sk_test_1234",
            "monthly_budget": "42.5",
        },
    )

    assert response.status_code == 200
    mock_configure.assert_called_once_with(
        api_key="pk_test_1234",
        api_secret="sk_test_1234",
        monthly_budget=42.5,
    )
    assert "Domain API configuration saved successfully" in response.get_data(as_text=True)


@patch("email_routes.domain_rotation_manager.rotate_domain", return_value="freshdomain.xyz")
def test_email_domain_rotate_form_post_redirects_with_message(_mock_rotate):
    client = _make_client()
    _init_session(client)

    response = client.post("/test-path/email/domain/rotate")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/test-path/email/config")

    follow = client.get(response.headers["Location"])
    assert follow.status_code == 200
    assert "Domain rotation successful: freshdomain.xyz" in follow.get_data(as_text=True)


@patch("email_routes.domain_rotation_manager.rotate_domain", return_value=None)
def test_email_domain_rotate_json_returns_failure_payload(_mock_rotate):
    client = _make_client()
    _init_session(client)

    response = client.post(
        "/test-path/email/domain/rotate",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "error" in payload
