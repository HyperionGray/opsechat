"""
Tests for operational endpoints registered by app_factory.
"""

from flask import Flask

from app_factory import register_operational_routes


def _build_app():
    app = Flask(__name__)
    register_operational_routes(app)
    return app


def test_version_endpoint_returns_200():
    client = _build_app().test_client()
    response = client.get("/version")
    assert response.status_code == 200


def test_version_endpoint_returns_json_version_string():
    client = _build_app().test_client()
    response = client.get("/version")
    data = response.get_json()
    assert data is not None
    assert "version" in data
    assert isinstance(data["version"], str)
    assert data["version"] != ""
