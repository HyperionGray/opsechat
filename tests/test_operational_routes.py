"""
Tests for operational endpoints registered by app_factory.
"""

from flask import Flask
import pytest

import datetime

from flask import Flask

from app_factory import register_operational_routes


@pytest.fixture
def client():
    app = Flask(__name__)
    register_operational_routes(app)
    return app.test_client()

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


def test_health_endpoint_returns_expected_payload_shape():
    client = _make_app().test_client()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data["status"] == "healthy"
    assert "version" in data
    assert "checks" in data


def test_chat_stats_endpoint_returns_expected_payload_shape():
    client = _make_app().test_client()
    response = client.get("/chat/stats")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert "active_rooms" in data
    assert "total_messages" in data
    assert "active_users" in data
    assert "pending_dms" in data
    assert "config" in data
