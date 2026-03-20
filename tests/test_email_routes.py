"""
Integration tests for email view/edit/delete routes.
"""

import pytest

from app_factory import create_app
from email_system import email_storage


@pytest.fixture(autouse=True)
def clear_email_storage():
    """Reset global in-memory email storage between tests."""
    email_storage.emails.clear()
    yield
    email_storage.emails.clear()


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["path"] = "test-path"
    application.config["hostname"] = "localhost"
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _seed_email(client, subject="Original Subject", body="Original body"):
    with client.session_transaction() as sess:
        sess["_id"] = "test-user"
        sess["color"] = "green"

    email_storage.create_user_inbox("test-user")
    email_storage.add_email(
        "test-user",
        {
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "subject": subject,
            "body": body,
            "sent": True,
        },
    )
    return email_storage.get_emails("test-user")[-1]["id"]


def test_email_view_existing_email_returns_200(client):
    email_id = _seed_email(client)
    response = client.get(f"/test-path/email/view/{email_id}")
    assert response.status_code == 200
    assert b"Original Subject" in response.data
    assert b"sender@example.com" in response.data


def test_email_view_nonexistent_email_returns_404(client):
    _seed_email(client)
    response = client.get("/test-path/email/view/no-such-email")
    assert response.status_code == 404


def test_email_edit_get_prefills_raw_content(client):
    email_id = _seed_email(client, subject="Raw Subject")
    response = client.get(f"/test-path/email/edit/{email_id}")
    assert response.status_code == 200
    assert b"Subject: Raw Subject" in response.data
    assert b"From: sender@example.com" in response.data


def test_email_edit_post_updates_email_and_redirects(client):
    email_id = _seed_email(client)
    updated_raw = (
        "From: edited@example.com\n"
        "To: recipient@example.com\n"
        "Subject: Updated Subject\n"
        "X-Test: Updated\n"
        "\n"
        "Updated email body"
    )

    response = client.post(
        f"/test-path/email/edit/{email_id}",
        data={"raw_email": updated_raw},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/test-path/email/view/{email_id}")

    updated = email_storage.get_email("test-user", email_id)
    assert updated is not None
    assert updated["from"] == "edited@example.com"
    assert updated["subject"] == "Updated Subject"
    assert updated["body"] == "Updated email body"
    assert updated["headers"]["X-Test"] == "Updated"


def test_email_edit_post_rejects_empty_raw_email(client):
    email_id = _seed_email(client)
    response = client.post(
        f"/test-path/email/edit/{email_id}",
        data={"raw_email": "   "},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"Raw email content cannot be empty." in response.data


def test_email_delete_removes_email_and_redirects(client):
    email_id = _seed_email(client)
    response = client.post(f"/test-path/email/delete/{email_id}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/test-path/email")
    assert email_storage.get_email("test-user", email_id) is None


def test_email_routes_reject_wrong_path(client):
    email_id = _seed_email(client)
    response = client.get(f"/wrong-path/email/view/{email_id}")
    assert response.status_code == 404
