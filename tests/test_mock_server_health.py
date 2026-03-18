import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_server  # noqa: E402


def test_health_email_endpoint_reports_backend_state():
    user_id = "health-check-user"
    mock_server.email_storage.create_user_inbox(user_id)
    mock_server.burner_manager.generate_burner_email(user_id)

    client = mock_server.app.test_client()
    response = client.get("/health/email")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["status"] == "ok"
    assert payload["server"] == "mock-opsechat"
    assert payload["backend"] in {"production", "fallback-mock"}
    assert "inbox_count" in payload
    assert "burner_count" in payload
    assert "burners_by_user" in payload
    assert payload["burners_by_user"].get(user_id, 0) >= 1
