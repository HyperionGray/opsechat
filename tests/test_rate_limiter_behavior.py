"""Rate limiter and security-header behavior tests."""

from app_factory import create_app
from simple_chat_routes import chat_rooms, direct_messages


def _create_room(client):
    response = client.post("/chat/create")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload and payload.get("room_id")
    return payload["room_id"]


def _post_message(client, room_id, message):
    return client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": message},
    )


def test_post_rate_limit_does_not_block_get_reads():
    app = create_app(
        {
            "TESTING": True,
            "RATE_LIMIT_CHAT_CREATE": "100 per minute",
            "RATE_LIMIT_CHAT_MESSAGES_POST": "3 per minute",
            "RATE_LIMIT_CHAT_DM_SEND": "100 per minute",
        }
    )

    chat_rooms.clear()
    direct_messages.clear()
    client = app.test_client()
    room_id = _create_room(client)

    for i in range(3):
        response = _post_message(client, room_id, f"msg-{i}")
        assert response.status_code == 200

    limited = _post_message(client, room_id, "msg-over-limit")
    assert limited.status_code == 429

    # GET reads are intentionally not rate-limited by this endpoint rule.
    read_response = client.get(f"/chat/room/{room_id}/messages")
    assert read_response.status_code == 200


def test_rate_limits_are_isolated_per_session_not_shared_ip():
    app = create_app(
        {
            "TESTING": True,
            "RATE_LIMIT_CHAT_CREATE": "100 per minute",
            "RATE_LIMIT_CHAT_MESSAGES_POST": "3 per minute",
            "RATE_LIMIT_CHAT_DM_SEND": "100 per minute",
        }
    )

    chat_rooms.clear()
    direct_messages.clear()
    client_a = app.test_client()
    client_b = app.test_client()
    room_id = _create_room(client_a)

    for i in range(3):
        response = _post_message(client_a, room_id, f"a-msg-{i}")
        assert response.status_code == 200

    limited = _post_message(client_a, room_id, "a-over-limit")
    assert limited.status_code == 429

    # Client B uses a different session and should not inherit A's limit bucket.
    fresh_session_response = _post_message(client_b, room_id, "b-first-message")
    assert fresh_session_response.status_code == 200


def test_security_headers_keep_same_origin_iframe_support():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/chat")
    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in response.headers.get("Content-Security-Policy", "")
