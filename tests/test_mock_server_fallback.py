"""
Tests for mock server fallback email/burner implementations.
"""

from tests import mock_server


def test_fallback_email_storage_creates_inbox():
    storage = mock_server.FallbackEmailStorage()
    storage.create_user_inbox("user1")
    assert "user1" in storage.emails
    assert storage.emails["user1"] == []


def test_fallback_burner_manager_lifecycle():
    manager = mock_server.FallbackBurnerManager()

    email = manager.generate_burner_email("user1")
    assert manager.get_user_for_burner(email) == "user1"

    burners = manager.get_user_burners("user1")
    assert len(burners) == 1
    assert burners[0]["email"] == email

    rotated = manager.rotate_burner("user1", old_email=email)
    assert rotated != email
    assert manager.get_user_for_burner(email) is None
    assert manager.get_user_for_burner(rotated) == "user1"

    assert manager.expire_burner(rotated) is True
    assert manager.get_user_for_burner(rotated) is None
    assert manager.expire_burner("missing@example.com") is False


def test_fallback_burner_manager_normalizes_invalid_hours():
    manager = mock_server.FallbackBurnerManager()

    email = manager.generate_burner_email("user2", hours_valid=0)
    assert manager.get_user_for_burner(email) == "user2"
