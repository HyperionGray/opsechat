import hashlib

from flask import Flask, session

from rate_limiter import get_session_or_ip_key


def create_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    return app


def test_get_session_or_ip_key_prefers_session_identity():
    app = create_test_app()

    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "198.51.100.7"}):
        session["_id"] = "chat-user-123"

        assert get_session_or_ip_key() == "session:chat-user-123"


def test_get_session_or_ip_key_hashes_session_cookie_when_identity_missing():
    app = create_test_app()
    raw_cookie = "signed-session-cookie"
    expected_hash = hashlib.sha256(raw_cookie.encode("utf-8")).hexdigest()

    with app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "198.51.100.7"},
        headers={"Cookie": f"session={raw_cookie}"},
    ):
        assert get_session_or_ip_key() == f"cookie:{expected_hash}"


def test_get_session_or_ip_key_falls_back_to_remote_ip():
    app = create_test_app()

    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "198.51.100.7"}):
        assert get_session_or_ip_key() == "ip:198.51.100.7"
