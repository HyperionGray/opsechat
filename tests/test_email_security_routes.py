"""
Tests for email_security_routes blueprint.
"""
from flask import Flask, session

from email_security_routes import create_email_security_blueprint


def _build_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    app.config["path"] = "test-path"
    app.config["hostname"] = "example.onion"
    app.register_blueprint(
        create_email_security_blueprint(
            id_generator=lambda: "test-user-id",
            get_random_color=lambda: [255, 0, 0],
        )
    )
    return app


def test_email_domain_rotate_returns_structured_result():
    app = _build_test_app()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_id"] = "test-user-id"

        response = client.post("/test-path/email/domain/rotate")
        assert response.status_code == 200
        data = response.get_json()
        assert "success" in data
        if data["success"]:
            assert "domain" in data
            assert "price" in data
        else:
            assert "error" in data
