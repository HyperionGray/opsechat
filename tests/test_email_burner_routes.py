"""
Integration tests for burner email routes in email_routes.py.
"""
import os
import sys
from urllib.parse import quote

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from email_system import burner_manager


@pytest.fixture(autouse=True)
def reset_burner_state():
    """Reset shared burner manager state between tests."""
    burner_manager.burner_addresses.clear()
    burner_manager.user_burners.clear()
    burner_manager.send_limits.clear()
    burner_manager.custom_domain = None
    yield
    burner_manager.burner_addresses.clear()
    burner_manager.user_burners.clear()
    burner_manager.send_limits.clear()
    burner_manager.custom_domain = None


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["path"] = "test-path-12345"
    app.config["hostname"] = "localhost"
    return app.test_client()


def test_burner_page_renders(client):
    response = client.get("/test-path-12345/email/burner")
    assert response.status_code == 200
    assert b"Burner Email Generator" in response.data


def test_generate_burner_then_list_json_has_stats(client):
    post_response = client.post(
        "/test-path-12345/email/burner",
        data={"action": "generate"},
    )
    assert post_response.status_code == 200

    list_response = client.get("/test-path-12345/email/burner/list.json")
    assert list_response.status_code == 200
    payload = list_response.get_json()

    assert "burners" in payload
    assert len(payload["burners"]) == 1
    assert "stats" in payload
    assert payload["stats"]["active_burners_count"] == 1
    assert "send_limit" in payload["stats"]


def test_rotate_burner_expires_old_and_keeps_single_active(client):
    client.post("/test-path-12345/email/burner", data={"action": "generate"})
    first_payload = client.get("/test-path-12345/email/burner/list.json").get_json()
    old_email = first_payload["burners"][0]["email"]

    rotate_response = client.post(
        "/test-path-12345/email/burner",
        data={"action": "rotate", "old_email": old_email},
    )
    assert rotate_response.status_code == 200

    second_payload = client.get("/test-path-12345/email/burner/list.json").get_json()
    assert len(second_payload["burners"]) == 1
    assert second_payload["burners"][0]["email"] != old_email


def test_expire_route_removes_burner(client):
    client.post("/test-path-12345/email/burner", data={"action": "generate"})
    payload = client.get("/test-path-12345/email/burner/list.json").get_json()
    burner_email = payload["burners"][0]["email"]

    expire_response = client.post(
        f"/test-path-12345/email/burner/expire/{quote(burner_email, safe='')}"
    )
    assert expire_response.status_code == 302

    post_expire_payload = client.get("/test-path-12345/email/burner/list.json").get_json()
    assert post_expire_payload["burners"] == []
