"""Regression coverage for PR #133 follow-up fixes."""

from app_factory import create_app
from simple_chat_routes import ENCRYPTED_MESSAGE_PREFIX


def _new_test_app():
    app = create_app()
    app.config["TESTING"] = True
    return app


def test_security_headers_allow_same_origin_iframes():
    app = _new_test_app()

    with app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    csp = response.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'self'" in csp


def test_chat_create_rate_limit_returns_429():
    app = _new_test_app()
    ip = "198.51.100.10"

    with app.test_client() as client:
        statuses = [
            client.post("/chat/create", environ_base={"REMOTE_ADDR": ip}).status_code
            for _ in range(4)
        ]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


def test_encrypted_payload_prefix_bypasses_plaintext_base64_block():
    app = _new_test_app()
    ip = "198.51.100.11"

    with app.test_client() as client:
        create_response = client.post("/chat/create", environ_base={"REMOTE_ADDR": ip})
        assert create_response.status_code == 200
        room_id = create_response.get_json()["room_id"]

        encrypted_message = ENCRYPTED_MESSAGE_PREFIX + ("A" * 600)
        post_response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": encrypted_message},
            environ_base={"REMOTE_ADDR": ip},
        )
        assert post_response.status_code == 200
        assert post_response.get_json()["success"] is True

        messages_response = client.get(
            f"/chat/room/{room_id}/messages",
            environ_base={"REMOTE_ADDR": ip},
        )
        assert messages_response.status_code == 200
        messages = messages_response.get_json()["messages"]
        assert messages[-1]["message"] == encrypted_message


def test_plaintext_base64_like_payload_is_still_blocked():
    app = _new_test_app()
    ip = "198.51.100.12"

    with app.test_client() as client:
        create_response = client.post("/chat/create", environ_base={"REMOTE_ADDR": ip})
        assert create_response.status_code == 200
        room_id = create_response.get_json()["room_id"]

        base64_like_plaintext = "A" * 150
        post_response = client.post(
            f"/chat/room/{room_id}/messages",
            json={"message": base64_like_plaintext},
            environ_base={"REMOTE_ADDR": ip},
        )

    assert post_response.status_code == 400
    assert "Invalid message format" in post_response.get_json()["error"]
