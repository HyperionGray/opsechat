"""
Tests for operational endpoints registered in app_factory.
"""

import datetime

from flask import Flask

from app_factory import register_operational_routes


def _make_app():
    app = Flask(__name__)
    register_operational_routes(app)
    return app


def test_version_endpoint_returns_200():
    client = _make_app().test_client()
    response = client.get("/version")
    assert response.status_code == 200


def test_version_endpoint_returns_json_fields():
    client = _make_app().test_client()
    data = client.get("/version").get_json()
    assert data is not None
    assert "version" in data
    assert "timestamp" in data
    assert isinstance(data["version"], str)


def test_version_endpoint_timestamp_is_iso8601_utc():
    client = _make_app().test_client()
    data = client.get("/version").get_json()
    parsed = datetime.datetime.fromisoformat(data["timestamp"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(0)


def test_version_matches_health_version():
    client = _make_app().test_client()
    version_data = client.get("/version").get_json()
    health_data = client.get("/health").get_json()
    assert version_data["version"] == health_data["version"]
