"""
Tests for the HTTP mail system (email over HTTP, no SMTP/IMAP).

Covers:
- HttpMailStorage: create mailbox, send, read (default deny), delete, destroy
- http_mail_routes: all REST endpoints via Flask test client
- Missing email_routes: view, edit, delete, burner POST, expire
"""

import datetime
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http_mail_system import (
    HttpMailStorage,
    HttpMailbox,
    HttpMessage,
    http_mail_storage,
    MAX_MAIL_MESSAGE_LENGTH,
)
from email_system import email_storage as _global_email_storage, EmailComposer
from app_factory import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


# ===========================================================================
# HttpMailStorage unit tests
# ===========================================================================

class TestHttpMailStorage:
    def setup_method(self):
        self.storage = HttpMailStorage()

    def test_create_mailbox_returns_mailbox(self):
        mb = self.storage.create_mailbox()
        assert mb is not None
        assert isinstance(mb, HttpMailbox)

    def test_mailbox_has_address_and_read_key(self):
        mb = self.storage.create_mailbox()
        assert mb.address
        assert mb.read_key
        assert mb.address != mb.read_key

    def test_address_is_12_chars(self):
        mb = self.storage.create_mailbox()
        # token_urlsafe(9) → 12 base64url chars
        assert len(mb.address) == 12

    def test_read_key_is_32_chars(self):
        mb = self.storage.create_mailbox()
        # token_urlsafe(24) → 32 base64url chars
        assert len(mb.read_key) == 32

    def test_unique_addresses(self):
        addresses = {self.storage.create_mailbox().address for _ in range(50)}
        assert len(addresses) == 50

    def test_get_mailbox_returns_correct_mailbox(self):
        mb = self.storage.create_mailbox()
        fetched = self.storage.get_mailbox(mb.address)
        assert fetched is mb

    def test_get_mailbox_nonexistent_returns_none(self):
        assert self.storage.get_mailbox("doesnotexist") is None

    def test_mailbox_count_increments(self):
        assert self.storage.mailbox_count() == 0
        self.storage.create_mailbox()
        assert self.storage.mailbox_count() == 1
        self.storage.create_mailbox()
        assert self.storage.mailbox_count() == 2

    def test_delete_mailbox_with_correct_key(self):
        mb = self.storage.create_mailbox()
        result = self.storage.delete_mailbox(mb.address, mb.read_key)
        assert result is True
        assert self.storage.get_mailbox(mb.address) is None

    def test_delete_mailbox_wrong_key_fails(self):
        mb = self.storage.create_mailbox()
        result = self.storage.delete_mailbox(mb.address, "wrongkey")
        assert result is False
        assert self.storage.get_mailbox(mb.address) is not None

    def test_delete_nonexistent_mailbox(self):
        result = self.storage.delete_mailbox("nope", "key")
        assert result is False

    def test_cleanup_empty_old_mailboxes(self):
        mb = self.storage.create_mailbox()
        # Backdate creation time to trigger cleanup
        mb.created_at = datetime.datetime.now() - datetime.timedelta(hours=49)
        self.storage.cleanup_empty_old_mailboxes()
        assert self.storage.get_mailbox(mb.address) is None

    def test_cleanup_preserves_mailbox_with_messages(self):
        mb = self.storage.create_mailbox()
        mb.created_at = datetime.datetime.now() - datetime.timedelta(hours=49)
        mb.add_message("subj", "body", "sender")
        self.storage.cleanup_empty_old_mailboxes()
        assert self.storage.get_mailbox(mb.address) is not None


# ===========================================================================
# HttpMailbox unit tests
# ===========================================================================

class TestHttpMailbox:
    def setup_method(self):
        self.mailbox = HttpMailbox(address="testaddr1", read_key="secretkey123456789012345678901")

    def test_add_message_returns_id(self):
        msg_id = self.mailbox.add_message("Hello", "Body text", "alice")
        assert msg_id
        assert len(msg_id) == 16

    def test_get_messages_correct_key(self):
        self.mailbox.add_message("Subj", "Body", "alice")
        msgs = self.mailbox.get_messages("secretkey123456789012345678901")
        assert msgs is not None
        assert len(msgs) == 1
        assert msgs[0]["subject"] == "Subj"
        assert msgs[0]["body"] == "Body"
        assert msgs[0]["sender"] == "alice"

    def test_get_messages_wrong_key_returns_none(self):
        self.mailbox.add_message("Subj", "Body", "alice")
        msgs = self.mailbox.get_messages("wrongkey")
        assert msgs is None

    def test_get_messages_empty_key_returns_none(self):
        msgs = self.mailbox.get_messages("")
        assert msgs is None

    def test_delete_message_correct_key(self):
        msg_id = self.mailbox.add_message("Subj", "Body", "alice")
        result = self.mailbox.delete_message("secretkey123456789012345678901", msg_id)
        assert result is True
        msgs = self.mailbox.get_messages("secretkey123456789012345678901")
        assert len(msgs) == 0

    def test_delete_message_wrong_key(self):
        msg_id = self.mailbox.add_message("Subj", "Body", "alice")
        result = self.mailbox.delete_message("wrongkey", msg_id)
        assert result is False
        msgs = self.mailbox.get_messages("secretkey123456789012345678901")
        assert len(msgs) == 1

    def test_delete_nonexistent_message(self):
        result = self.mailbox.delete_message("secretkey123456789012345678901", "fakeid")
        assert result is False

    def test_message_expiry(self):
        self.mailbox.add_message("Old", "Old body", "bob")
        # Backdate the message timestamp
        self.mailbox.messages[0].timestamp = (
            datetime.datetime.now() - datetime.timedelta(hours=25)
        )
        msgs = self.mailbox.get_messages("secretkey123456789012345678901")
        assert msgs == []

    def test_message_count(self):
        assert self.mailbox.message_count() == 0
        self.mailbox.add_message("A", "B", "c")
        assert self.mailbox.message_count() == 1

    def test_message_to_dict_has_required_fields(self):
        self.mailbox.add_message("Subject", "Body", "sender")
        msgs = self.mailbox.get_messages("secretkey123456789012345678901")
        m = msgs[0]
        assert "id" in m
        assert "subject" in m
        assert "body" in m
        assert "sender" in m
        assert "timestamp" in m

    def test_overwrite_clears_content(self):
        msg = HttpMessage("id1", "Secret Subject", "Secret Body", "Alice",
                          datetime.datetime.now())
        msg.overwrite()
        assert "Secret" not in msg.subject
        assert "Secret" not in msg.body
        assert "Alice" not in msg.sender_handle


# ===========================================================================
# HTTP mail route integration tests
# ===========================================================================

class TestHttpMailRoutes:
    def setup_method(self):
        self.app = _fresh_app()
        self.client = self.app.test_client()
        # Inject a known path into the app config
        self.app.config["path"] = "secpath"
        self.app.config["hostname"] = "localhost"
        self.path = "secpath"

    def test_mail_index_returns_200(self):
        r = self.client.get(f"/{self.path}/mail")
        assert r.status_code == 200

    def test_mail_index_wrong_path_404(self):
        r = self.client.get("/wrongpath/mail")
        assert r.status_code == 404

    def test_create_mailbox_returns_success(self):
        r = self.client.post(f"/{self.path}/mail/new")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert "address" in data
        assert "read_key" in data

    def test_create_mailbox_returns_send_and_inbox_urls(self):
        r = self.client.post(f"/{self.path}/mail/new")
        data = r.get_json()
        assert "send_url" in data
        assert "inbox_url" in data
        assert data["send_url"].startswith(f"/{self.path}/mail/")
        assert data["inbox_url"].endswith("/inbox")

    def test_send_message_json(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]

        r = self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "Hi", "body": "Hello there", "sender": "bob"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert "msg_id" in data

    def test_send_message_empty_body_fails(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        r = self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "X", "body": "", "sender": "bob"},
        )
        assert r.status_code == 400

    def test_send_to_nonexistent_mailbox(self):
        r = self.client.post(
            f"/{self.path}/mail/doesnotexist/send",
            json={"subject": "X", "body": "Y", "sender": "bob"},
        )
        assert r.status_code == 404

    def test_read_inbox_correct_key(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "Test", "body": "Hello", "sender": "alice"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["subject"] == "Test"

    def test_read_inbox_wrong_key_is_denied(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key=wrongkey",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403

    def test_read_inbox_no_key_is_denied(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403

    def test_read_inbox_nonexistent_mailbox(self):
        r = self.client.get(
            f"/{self.path}/mail/doesnotexist/inbox?key=anykey",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 404

    def test_delete_message_correct_key(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "Del", "body": "Body", "sender": "x"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        msg_id = r.get_json()["messages"][0]["id"]

        r = self.client.post(
            f"/{self.path}/mail/{addr}/delete/{msg_id}",
            json={"read_key": read_key},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True

        # Verify deleted
        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        assert len(r.get_json()["messages"]) == 0

    def test_delete_message_wrong_key(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"body": "Body", "sender": "x"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        msg_id = r.get_json()["messages"][0]["id"]

        r = self.client.post(
            f"/{self.path}/mail/{addr}/delete/{msg_id}",
            json={"read_key": "wrongkey"},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403

    def test_destroy_mailbox_correct_key(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        r = self.client.post(
            f"/{self.path}/mail/{addr}/destroy",
            json={"read_key": read_key},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True

    def test_destroy_mailbox_wrong_key(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]

        r = self.client.post(
            f"/{self.path}/mail/{addr}/destroy",
            json={"read_key": "badkey"},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403

    def test_message_body_sanitized(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "<script>alert(1)</script>", "body": "<b>bold</b>", "sender": "x"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        msgs = r.get_json()["messages"]
        assert "<script>" not in msgs[0]["subject"]
        assert "<b>" not in msgs[0]["body"]

    def test_empty_sender_defaults_to_anonymous(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"body": "Hi", "sender": ""},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        assert r.get_json()["messages"][0]["sender"] == "anonymous"

    def test_send_message_form_fallback_route(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        r = self.client.post(
            f"/{self.path}/mail/send",
            data={
                "_address_override": addr,
                "subject": "Fallback",
                "body": "Form send works",
                "sender": "form-user",
            },
        )
        assert r.status_code == 200
        assert b"Message sent." in r.data

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}",
            headers={"Accept": "application/json"},
        )
        messages = r.get_json()["messages"]
        assert len(messages) == 1
        assert messages[0]["subject"] == "Fallback"

    def test_send_message_form_fallback_requires_address(self):
        r = self.client.post(
            f"/{self.path}/mail/send",
            data={"subject": "No address", "body": "X"},
        )
        assert r.status_code == 400
        assert b"Recipient mailbox address is required" in r.data

    def test_read_inbox_json_supports_limit_offset(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        for idx in range(3):
            self.client.post(
                f"/{self.path}/mail/{addr}/send",
                json={"subject": f"S{idx}", "body": f"Body {idx}", "sender": "alice"},
            )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}&limit=2&offset=1",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["total_messages"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert data["has_more"] is False
        assert [m["subject"] for m in data["messages"]] == ["S1", "S2"]

    def test_read_inbox_json_include_body_false_hides_body(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "Hidden body", "body": "secret", "sender": "alice"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}&include_body=false",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        msg = r.get_json()["messages"][0]
        assert "body" not in msg

    def test_read_inbox_json_invalid_limit_returns_400(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        r = self.client.get(
            f"/{self.path}/mail/{addr}/inbox?key={read_key}&limit=0",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 400
        assert "limit must be >=" in r.get_json()["error"]

    def test_mailbox_status_endpoint(self):
        r = self.client.post(f"/{self.path}/mail/new")
        addr = r.get_json()["address"]
        read_key = r.get_json()["read_key"]

        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "A", "body": "B", "sender": "alice"},
        )
        self.client.post(
            f"/{self.path}/mail/{addr}/send",
            json={"subject": "C", "body": "D", "sender": "alice"},
        )

        r = self.client.get(
            f"/{self.path}/mail/{addr}/status?key={read_key}",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["message_count"] == 2
        assert data["oldest_message_at"] is not None
        assert data["newest_message_at"] is not None

        r = self.client.get(
            f"/{self.path}/mail/{addr}/status?key=wrong",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 403


# ===========================================================================
# Missing email route tests (view, edit, delete, burner POST, expire)
# ===========================================================================

class TestEmailRoutesExtended:
    def setup_method(self):
        self.app = _fresh_app()
        self.app.config["path"] = "secpath"
        self.app.config["hostname"] = "localhost"
        self.client = self.app.test_client()

        # Set up a session with a known user_id
        with self.client.session_transaction() as sess:
            sess["_id"] = "testuser99"
            sess["color"] = "green"

        # Pre-populate an email in the storage for testuser99
        _global_email_storage.create_user_inbox("testuser99")
        _global_email_storage.add_email("testuser99", {
            "from": "sender@example.com",
            "to": "me@example.com",
            "subject": "Hello",
            "body": "Test body",
            "is_pgp": False,
            "headers": {},
        })
        self.email_id = _global_email_storage.emails["testuser99"][0]["id"]

    def teardown_method(self):
        # Clean up global state
        if "testuser99" in _global_email_storage.emails:
            _global_email_storage.emails["testuser99"] = []

    def test_view_email_returns_200(self):
        r = self.client.get(f"/secpath/email/view/{self.email_id}")
        assert r.status_code == 200
        assert b"Hello" in r.data

    def test_view_nonexistent_email_returns_404(self):
        r = self.client.get("/secpath/email/view/doesnotexist")
        assert r.status_code == 404

    def test_edit_email_get_returns_200(self):
        r = self.client.get(f"/secpath/email/edit/{self.email_id}")
        assert r.status_code == 200

    def test_edit_email_post_saves_and_redirects(self):
        raw = "From: new@example.com\nTo: me@example.com\nSubject: Updated\n\nNew body"
        r = self.client.post(
            f"/secpath/email/edit/{self.email_id}",
            data={"raw_email": raw},
        )
        assert r.status_code == 302

        # Verify update was applied
        updated = _global_email_storage.get_email("testuser99", self.email_id)
        assert updated["subject"] == "Updated"
        assert updated["body"] == "New body"

    def test_delete_email_removes_it(self):
        r = self.client.post(f"/secpath/email/delete/{self.email_id}")
        assert r.status_code == 302
        assert _global_email_storage.get_email("testuser99", self.email_id) is None

    def test_burner_generate_post_redirects(self):
        r = self.client.post("/secpath/email/burner", data={"action": "generate"})
        assert r.status_code == 302

    def test_burner_wrong_path_404(self):
        r = self.client.post("/wrongpath/email/burner", data={"action": "generate"})
        assert r.status_code == 404
