"""
Tests for email configuration and domain rotation routes.
"""
from unittest.mock import patch

import pytest

from app_factory import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["path"] = "testpath"
    application.config["hostname"] = "localhost"
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with app.app_context():
            yield c


def test_email_config_get_renders(client):
    response = client.get("/testpath/email/config")
    assert response.status_code == 200
    assert b"Email System Configuration" in response.data


def test_email_config_post_configure_domain(client):
    response = client.post(
        "/testpath/email/config",
        data={
            "action": "configure_domain_api",
            "api_key": "pk1_test_key",
            "api_secret": "sk1_test_secret",
            "monthly_budget": "15.00",
            "provider": "porkbun",
        },
    )
    assert response.status_code == 200
    assert b"Domain registrar configuration saved successfully" in response.data


def test_email_domain_rotate_json_success(client):
    with patch("email_routes.domain_rotation_manager.rotate_to_new_domain") as mock_rotate, \
         patch("email_routes.burner_manager.set_custom_domain") as mock_set_domain:
        mock_rotate.return_value = {"success": True, "domain": "rotated-test.xyz", "price": 1.99}
        response = client.post("/testpath/email/domain/rotate", json={})

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    mock_set_domain.assert_called_once_with("rotated-test.xyz")


def test_email_domain_rotate_form_failure_sets_message(client):
    with patch("email_routes.domain_rotation_manager.rotate_to_new_domain") as mock_rotate:
        mock_rotate.return_value = {"success": False, "error": "No cheap available domain found"}
        response = client.post("/testpath/email/domain/rotate", data={})

    # Form path redirects back to /email/config and stores message in session.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/testpath/email/config")
