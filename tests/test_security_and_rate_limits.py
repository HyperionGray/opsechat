from app_factory import create_app


def _create_test_client():
    app = create_app(
        {
            "TESTING": True,
            "RATE_LIMIT_CHAT_CREATE": "2 per minute",
            "RATELIMIT_DEFAULT": ["1000 per hour"],
        }
    )
    return app.test_client()


def test_security_headers_allow_same_origin_framing():
    client = _create_test_client()

    response = client.get("/chat")
    csp = response.headers.get("Content-Security-Policy", "")

    assert response.status_code == 200
    assert "frame-ancestors 'self'" in csp
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


def test_chat_create_rate_limit_returns_structured_429():
    client = _create_test_client()

    first = client.post("/chat/create")
    second = client.post("/chat/create")
    blocked = client.post("/chat/create")

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.is_json
    assert blocked.get_json() == {"error": "Rate limit exceeded. Please retry later."}
