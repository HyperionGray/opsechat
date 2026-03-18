"""
Tests for observability endpoints (/version and /metrics).
"""

import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from monitoring import apm


def _new_client():
    app = create_app()
    return app.test_client()


def setup_function():
    """Reset global metrics state between tests."""
    apm.reset_metrics()


def test_version_endpoint_returns_version_and_status():
    client = _new_client()
    response = client.get("/version")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert isinstance(data["version"], str)
    assert data["version"] != ""


def test_metrics_endpoint_returns_expected_top_level_fields():
    client = _new_client()
    response = client.get("/metrics")
    data = response.get_json()

    assert response.status_code == 200
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "requests" in data
    assert "tor" in data
    assert "activity" in data


def test_metrics_endpoint_detailed_normalizes_dynamic_path_segments():
    client = _new_client()

    # Trigger a dynamic URL path with a long token-like segment.
    client.get("/chat/room/abcd1234abcd1234abcd1234abcd1234/messages")

    metrics_response = client.get("/metrics?detailed=1")
    metrics = metrics_response.get_json()
    by_endpoint = metrics["requests"]["by_endpoint"]

    assert "GET /chat/room/:id/messages" in by_endpoint
    assert by_endpoint["GET /chat/room/:id/messages"]["count"] >= 1
