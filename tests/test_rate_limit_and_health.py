"""
Tests for rate limiting (simple_chat_routes) and the /health endpoint (app_factory).
"""

import datetime
import sys
import os

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
from simple_chat_routes import check_rate_limit, _rate_limit_store, _rate_limit_lock
from monitoring import _scan_template_release_readiness

# Shared test Flask app (avoids importing all of runserver.py)
_test_app = create_app()


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------

def _clear_store():
    """Helper: wipe the rate limit store between tests."""
    with _rate_limit_lock:
        _rate_limit_store.clear()


def test_rate_limit_allows_requests_within_window():
    _clear_store()
    for _ in range(5):
        allowed, retry_after = check_rate_limit("session-1", "dm_send")
        assert allowed is True
        assert retry_after == 0


def test_rate_limit_blocks_when_exceeded():
    _clear_store()
    # dm_send: 5 requests per 60 seconds
    for _ in range(5):
        check_rate_limit("session-block", "dm_send")
    allowed, retry_after = check_rate_limit("session-block", "dm_send")
    assert allowed is False
    assert retry_after >= 1


def test_rate_limit_tracks_sessions_independently():
    _clear_store()
    # Exhaust session-a
    for _ in range(5):
        check_rate_limit("session-a", "dm_send")
    # session-b should still be allowed
    allowed, _ = check_rate_limit("session-b", "dm_send")
    assert allowed is True


def test_rate_limit_resets_after_window():
    _clear_store()
    sid = "session-expire"
    # Backdate all existing timestamps so they fall outside the window
    with _rate_limit_lock:
        _rate_limit_store[sid] = {
            "dm_send": [
                datetime.datetime.now() - datetime.timedelta(seconds=120)
            ] * 5
        }
    allowed, retry_after = check_rate_limit(sid, "dm_send")
    assert allowed is True
    assert retry_after == 0


def test_rate_limit_unknown_endpoint_always_allows():
    _clear_store()
    for _ in range(100):
        allowed, _ = check_rate_limit("session-x", "nonexistent_endpoint")
        assert allowed is True


def test_rate_limit_chat_message_limit():
    _clear_store()
    # chat_message: 30 requests per 60 seconds
    for _ in range(30):
        allowed, _ = check_rate_limit("session-msg", "chat_message")
        assert allowed is True
    allowed, retry_after = check_rate_limit("session-msg", "chat_message")
    assert allowed is False
    assert retry_after >= 1


# ---------------------------------------------------------------------------
# Health endpoint integration tests
# ---------------------------------------------------------------------------

def test_health_endpoint_returns_200():
    client = _test_app.test_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_json_with_required_fields():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert data is not None
    assert data.get("status") == "healthy"
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert "version" in data
    assert "active_rooms" in data
    assert "checks" in data


def test_health_endpoint_active_rooms_is_integer():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()
    assert isinstance(data["active_rooms"], int)
    assert data["active_rooms"] >= 0


def test_health_endpoint_timestamp_is_iso8601_utc():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    parsed = datetime.datetime.fromisoformat(data["timestamp"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(0)


def test_health_endpoint_reports_non_negative_uptime():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_health_endpoint_includes_expected_checks():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    assert data["checks"]["tor_connection"] == "unknown"
    assert data["checks"]["memory_usage"] == "ok"
    assert data["checks"]["disk_space"] == "ok"
    assert data["checks"]["template_csp_readiness"] in {"ready", "action_required", "unknown"}


def test_health_endpoint_includes_release_readiness_template_audit():
    client = _test_app.test_client()
    response = client.get("/health")
    data = response.get_json()

    assert "release_readiness" in data
    assert "template_csp_audit" in data["release_readiness"]

    audit = data["release_readiness"]["template_csp_audit"]
    assert audit["status"] in {"ready", "action_required", "unknown"}
    assert "summary" in audit
    assert "templates_scanned" in audit["summary"]
    assert "inline_script_tags" in audit["summary"]
    assert "inline_style_attributes" in audit["summary"]
    assert "inline_event_handlers" in audit["summary"]
    assert "issues" in audit


def test_health_endpoint_sets_json_and_security_headers():
    client = _test_app.test_client()
    response = client.get("/health")

    assert response.content_type == "application/json"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Server"] == ""


def test_health_endpoint_date_header_is_blank():
    client = _test_app.test_client()
    response = client.get("/health")

    assert response.headers["Date"] == ""


def test_template_readiness_scan_detects_inline_markup(tmp_path):
    template_file = tmp_path / "inline.html"
    template_file.write_text(
        "<html><body>"
        "<script>console.log('inline')</script>"
        "<div style='color:red' onclick='doThing()'>x</div>"
        "</body></html>",
        encoding="utf-8",
    )

    audit = _scan_template_release_readiness(tmp_path)
    assert audit["status"] == "action_required"
    assert audit["summary"]["templates_scanned"] == 1
    assert audit["summary"]["inline_script_tags"] == 1
    assert audit["summary"]["inline_style_attributes"] == 1
    assert audit["summary"]["inline_event_handlers"] == 1
    assert len(audit["issues"]) == 1


def test_template_readiness_scan_ready_when_templates_are_externalized(tmp_path):
    template_file = tmp_path / "clean.html"
    template_file.write_text(
        "<html><head><script src='/static/app.js'></script></head>"
        "<body><main>ok</main></body></html>",
        encoding="utf-8",
    )

    audit = _scan_template_release_readiness(tmp_path)
    assert audit["status"] == "ready"
    assert audit["summary"]["templates_scanned"] == 1
    assert audit["summary"]["inline_script_tags"] == 0
    assert audit["summary"]["inline_style_attributes"] == 0
    assert audit["summary"]["inline_event_handlers"] == 0
    assert audit["issues"] == []
