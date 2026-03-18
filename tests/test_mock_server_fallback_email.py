"""
Tests for mock server fallback email components.
"""

from tests.mock_server import (
    InMemoryFallbackBurnerManager,
    InMemoryFallbackEmailStorage,
    create_fallback_email_components,
)


class TestMockServerFallbackEmailStorage:
    def test_create_user_inbox_is_idempotent(self):
        storage = InMemoryFallbackEmailStorage()

        inbox_first = storage.create_user_inbox("alice")
        inbox_second = storage.create_user_inbox("alice")

        assert "alice" in storage.inboxes
        assert inbox_first is inbox_second
        assert inbox_second == []


class TestMockServerFallbackBurnerManager:
    def test_generate_and_resolve_burner_email(self):
        manager = InMemoryFallbackBurnerManager()

        burner = manager.generate_burner_email("alice")
        owner = manager.get_user_for_burner(burner)
        user_burners = manager.get_user_burners("alice")

        assert burner.endswith("@example.com")
        assert owner == "alice"
        assert len(user_burners) == 1
        assert user_burners[0]["email"] == burner
        assert user_burners[0]["is_expired"] is False

    def test_rotate_burner_expires_old_when_owned_by_user(self):
        manager = InMemoryFallbackBurnerManager()

        old_burner = manager.generate_burner_email("alice")
        new_burner = manager.rotate_burner("alice", old_burner)

        assert new_burner != old_burner
        assert manager.get_user_for_burner(old_burner) is None
        assert manager.get_user_for_burner(new_burner) == "alice"

    def test_cleanup_expired_removes_stale_burners(self):
        manager = InMemoryFallbackBurnerManager()
        burner = manager.generate_burner_email("alice")

        # Force expiration without waiting in test runtime.
        manager._burners[burner]["expires_at"] = manager._burners[burner]["created_at"]
        manager.cleanup_expired()

        assert manager.get_user_for_burner(burner) is None
        assert manager.get_user_burners("alice") == []


def test_create_fallback_email_components_returns_expected_types():
    email_storage, burner_manager = create_fallback_email_components()

    assert isinstance(email_storage, InMemoryFallbackEmailStorage)
    assert isinstance(burner_manager, InMemoryFallbackBurnerManager)
