"""
Integration tests for burner routes in mock_routes.
"""

from flask import Flask

from tests.mock_email_backend import MockBurnerManager
from tests.mock_routes import create_mock_routes


def build_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    app.config["hostname"] = "localhost"
    app.config["path"] = "test-path-12345"

    chatters = []
    chatlines = []
    reviews = []
    counter = {"value": 0}

    def id_generator(size=6, chars=None):  # pylint: disable=unused-argument
        counter["value"] += 1
        return f"user{counter['value']}"

    def get_random_color():
        return "blue"

    manager = MockBurnerManager()
    create_mock_routes(
        app,
        chatters,
        chatlines,
        reviews,
        id_generator,
        get_random_color,
        burner_manager=manager,
    )
    return app


def test_burner_generate_and_list_flow():
    app = build_app()
    client = app.test_client()

    landing = client.get("/test-path-12345/email/burner")
    assert landing.status_code == 200

    generated = client.post("/test-path-12345/email/burner", data={"action": "generate"})
    assert generated.status_code == 200
    payload = generated.get_json()
    assert payload["success"] is True
    assert "email" in payload

    listed = client.get("/test-path-12345/email/burner/list")
    assert listed.status_code == 200
    burners = listed.get_json()
    assert isinstance(burners, list)
    assert len(burners) == 1
    assert burners[0]["email"] == payload["email"]


def test_burner_compatibility_routes():
    app = build_app()
    client = app.test_client()

    # Establish session and verify yesscript route.
    client.get("/test-path-12345/email/burner")
    scripted = client.get("/test-path-12345/email/burner/yesscript")
    assert scripted.status_code == 200

    generated = client.post("/test-path-12345/email/burner/generate")
    assert generated.status_code == 200
    payload = generated.get_json()
    assert payload["success"] is True
    assert payload["email"].endswith("@example.com")
