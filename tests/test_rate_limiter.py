#!/usr/bin/env python3
"""
Integration tests for Flask-Limiter rate limiting behavior.

Tests:
1. Write (POST) endpoints are rate-limited; read (GET) endpoints are not.
2. Two different client sessions do not share rate-limit counters.
"""

import json
import sys


def _make_app():
    """Return a fresh Flask test app with rate limiter enabled."""
    from app_factory import create_app
    app = create_app()
    app.config["TESTING"] = True
    # Disable the security-warning session flag so chat room pages render
    app.config["SECRET_KEY"] = "test-secret"
    return app


def test_post_is_rate_limited_get_is_not():
    """POST /chat/create is rate-limited; GET / is never rate-limited."""
    print("\nTesting: POST is rate-limited, GET is not...")
    app = _make_app()

    with app.test_client() as client:
        # GET / should never be throttled
        for _ in range(10):
            r = client.get("/")
            assert r.status_code == 200, f"GET / should never be throttled, got {r.status_code}"

        # POST /chat/create: limit is 3 per minute per client.
        # First 3 calls must succeed; the 4th must be rejected with 429.
        for i in range(3):
            r = client.post("/chat/create", content_type="application/json")
            assert r.status_code == 200, f"Request {i + 1} should succeed, got {r.status_code}"

        r = client.post("/chat/create", content_type="application/json")
        assert r.status_code == 429, f"4th POST should be rate-limited (429), got {r.status_code}"
        payload = r.get_json()
        assert payload is not None, "429 response should be JSON for chat endpoints"
        assert payload.get("retry_after", 0) >= 1
        assert int(r.headers.get("Retry-After", "0")) >= 1

    print("✅ POST /chat/create is rate-limited after 3 requests; GET / is never throttled")


def test_separate_sessions_have_independent_limits():
    """Two different sessions must not share rate-limit counters."""
    print("\nTesting: independent rate-limit counters per session...")
    app = _make_app()

    with app.test_client() as client_a:
        # Exhaust session A's limit (3 per minute)
        for i in range(3):
            r = client_a.post("/chat/create", content_type="application/json")
            assert r.status_code == 200, f"Client A request {i + 1} failed: {r.status_code}"

        # Session A must now be blocked
        r = client_a.post("/chat/create", content_type="application/json")
        assert r.status_code == 429, f"Client A should be blocked, got {r.status_code}"

    # A new test client gets a fresh session with its own counter
    with app.test_client() as client_b:
        r = client_b.post("/chat/create", content_type="application/json")
        assert r.status_code == 200, (
            f"Client B should NOT be blocked by Client A's exhausted limit, got {r.status_code}"
        )

    print("✅ Different sessions have independent rate-limit counters")


def main():
    print("=== Rate Limiter Integration Tests ===\n")
    results = []

    tests = [
        test_post_is_rate_limited_get_is_not,
        test_separate_sessions_have_independent_limits,
    ]

    for test_fn in tests:
        try:
            results.append(test_fn())
        except AssertionError as exc:
            print(f"❌ {test_fn.__name__} FAILED: {exc}")
            results.append(False)
        except Exception as exc:
            print(f"❌ {test_fn.__name__} ERROR: {exc}")
            results.append(False)

    print(f"\n=== Results: {sum(results)}/{len(results)} passed ===")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
