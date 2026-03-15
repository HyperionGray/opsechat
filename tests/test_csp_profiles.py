import re

from app_factory import create_app


def create_test_client():
    app = create_app()
    app.config.update(path="test-path-12345", hostname="localhost")
    return app.test_client()


def test_chat_routes_use_strict_csp_profile():
    client = create_test_client()
    response = client.get("/chat")

    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self';" in csp
    assert "style-src 'self';" in csp
    assert "'unsafe-inline'" not in csp


def test_legacy_routes_use_compatibility_csp_profile():
    client = create_test_client()
    response = client.get("/test-path-12345")

    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self' 'unsafe-inline';" in csp
    assert "style-src 'self' 'unsafe-inline';" in csp


def test_simple_chat_templates_load_static_assets_only():
    client = create_test_client()

    index_response = client.get("/chat")
    index_html = index_response.data.decode("utf-8")
    assert "/static/chat/simple_chat_index.css" in index_html
    assert "/static/chat/simple_chat_index.js" in index_html
    assert "<style" not in index_html.lower()
    assert re.search(r"<script(?![^>]*\bsrc=)", index_html, re.IGNORECASE) is None

    create_room_response = client.post("/chat/create")
    room_id = create_room_response.get_json()["room_id"]
    room_response = client.get(f"/chat/room/{room_id}")
    room_html = room_response.data.decode("utf-8")
    assert "/static/chat/simple_chat_room.css" in room_html
    assert "/static/chat/simple_chat_room.js" in room_html
    assert "<style" not in room_html.lower()
    assert re.search(r"<script(?![^>]*\bsrc=)", room_html, re.IGNORECASE) is None

    error_response = client.get("/chat/room/does-not-exist")
    error_html = error_response.data.decode("utf-8")
    assert error_response.status_code == 404
    assert "/static/chat/simple_chat_error.css" in error_html


def test_encrypted_chat_payloads_are_allowed_with_ascii_safe_prefix():
    client = create_test_client()
    create_room_response = client.post("/chat/create")
    room_id = create_room_response.get_json()["room_id"]

    encrypted_like_message = "ENC:" + ("A" * 160)
    post_response = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": encrypted_like_message},
    )
    assert post_response.status_code == 200

    invalid_encrypted_message = "ENC:not-valid-***"
    invalid_response = client.post(
        f"/chat/room/{room_id}/messages",
        json={"message": invalid_encrypted_message},
    )
    assert invalid_response.status_code == 400
