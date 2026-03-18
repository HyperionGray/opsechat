"""
Tests for mock server burner email endpoints.
"""

from urllib.parse import quote

from flask import Flask

from email_system import BurnerEmailManager, EmailStorage
from tests.mock_routes import create_mock_routes


def build_mock_app():
    """Create an isolated app instance with mock routes registered."""
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    app.config["hostname"] = "localhost"
    app.config["path"] = "test-path-12345"

    create_mock_routes(
        app,
        chatters=[],
        chatlines=[],
        reviews=[],
        id_generator=lambda size=6, chars=None: "abc123xyz789"[:size],
        get_random_color=lambda: "blue",
        email_storage=EmailStorage(),
        burner_manager=BurnerEmailManager(),
    )
    return app


def test_burner_route_post_generate_and_list():
    app = build_mock_app()
    client = app.test_client()

    first = client.get("/test-path-12345/email/burner")
    assert first.status_code == 200

    generate = client.post(
        "/test-path-12345/email/burner",
        data={"action": "generate"},
        follow_redirects=False,
    )
    assert generate.status_code == 302

    listing = client.get("/test-path-12345/email/burner/list")
    assert listing.status_code == 200
    data = listing.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "email" in data[0]


def test_burner_generate_endpoint_returns_email_payload():
    app = build_mock_app()
    client = app.test_client()

    response = client.post("/test-path-12345/email/burner/generate")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "@" in payload["email"]
    assert len(payload["active_burners"]) == 1


def test_burner_expire_requires_owner_session():
    app = build_mock_app()
    owner = app.test_client()
    attacker = app.test_client()

    created = owner.post("/test-path-12345/email/burner/generate")
    email = created.get_json()["email"]
    encoded_email = quote(email, safe="")

    # Different session should be rejected.
    forbidden = attacker.post(f"/test-path-12345/email/burner/expire/{encoded_email}")
    assert forbidden.status_code == 403

    # Owner can expire and list should then be empty.
    expired = owner.post(f"/test-path-12345/email/burner/expire/{encoded_email}")
    assert expired.status_code == 200
    assert expired.get_json()["success"] is True

    listing = owner.get("/test-path-12345/email/burner/list")
    assert listing.get_json() == []
