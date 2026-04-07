"""
Integration tests for review routes and session review activity.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-review-secret"
    app.config["hostname"] = "localhost"
    app.config["path"] = "test-path-12345"
    return app


def test_reviews_list_returns_normalized_review_payload():
    client = _fresh_app().test_client()

    # initialize session
    page_response = client.get("/test-path-12345/reviews")
    assert page_response.status_code == 200

    submit_response = client.post(
        "/test-path-12345/reviews/submit",
        data={"rating": "5", "review_text": "Excellent service"},
    )
    assert submit_response.status_code == 200
    assert submit_response.get_json()["success"] is True

    list_response = client.get("/test-path-12345/reviews/list")
    assert list_response.status_code == 200

    payload = list_response.get_json()
    assert "reviews" in payload
    assert "stats" in payload
    assert "my_review_count" in payload
    assert payload["stats"]["my_review_count"] == payload["my_review_count"] == 1
    assert len(payload["reviews"]) == 1
    assert payload["reviews"][0]["text"] == "Excellent service"
    assert payload["reviews"][0]["rating"] == 5


def test_reviews_me_reports_session_review_count():
    client = _fresh_app().test_client()

    # Start session and submit two reviews in same client session.
    assert client.get("/test-path-12345/reviews").status_code == 200
    assert client.post(
        "/test-path-12345/reviews/submit",
        data={"rating": "4", "review_text": "Good"},
    ).status_code == 200
    assert client.post(
        "/test-path-12345/reviews/submit",
        data={"rating": "3", "review_text": "Average"},
    ).status_code == 200

    response = client.get("/test-path-12345/reviews/me")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["my_review_count"] == 2


def test_reviews_me_without_session_returns_400():
    client = _fresh_app().test_client()

    response = client.get("/test-path-12345/reviews/me")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
