"""
Tests for mock email backend used by mock_server fallback mode.
"""

import datetime
from tests.mock_email_backend import MockEmailStorage, MockBurnerManager


class TestMockEmailStorage:
    def test_create_and_add_email(self):
        storage = MockEmailStorage()
        storage.create_user_inbox("u1")
        stored = storage.add_email("u1", {"subject": "hello"})

        assert "u1" in storage.emails
        assert stored["subject"] == "hello"
        assert "id" in stored
        assert "timestamp" in stored


class TestMockBurnerManager:
    def test_generate_and_lookup_user(self):
        manager = MockBurnerManager()
        email = manager.generate_burner_email("u1")

        assert email.endswith("@example.com")
        assert manager.get_user_for_burner(email) == "u1"

    def test_cleanup_expired_removes_indexes(self):
        manager = MockBurnerManager()
        email = manager.generate_burner_email("u1")
        manager.burner_addresses[email]["expires_at"] = (
            datetime.datetime.now() - datetime.timedelta(minutes=1)
        )

        manager.cleanup_expired()

        assert email not in manager.burner_addresses
        assert "u1" not in manager.user_burners

    def test_rotate_replaces_old_email(self):
        manager = MockBurnerManager()
        old_email = manager.generate_burner_email("u1")
        new_email = manager.rotate_burner("u1", old_email)

        assert new_email != old_email
        assert old_email not in manager.burner_addresses
        assert new_email in manager.burner_addresses
