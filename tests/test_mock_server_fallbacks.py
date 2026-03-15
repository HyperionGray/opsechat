import datetime

from tests.mock_server import MockBurnerManager, MockEmailStorage


def test_mock_email_storage_creates_and_reads_inboxes():
    storage = MockEmailStorage()

    storage.create_user_inbox("user-a")
    storage.add_email("user-a", {"subject": "hello"})

    inbox = storage.get_user_inbox("user-a")
    assert len(inbox) == 1
    assert inbox[0]["subject"] == "hello"


def test_mock_burner_manager_generate_rotate_and_expire():
    manager = MockBurnerManager()

    first = manager.generate_burner_email("user-a")
    assert manager.get_user_for_burner(first) == "user-a"
    assert first in manager.get_user_burners("user-a")

    rotated = manager.rotate_burner("user-a", first)
    assert rotated != first
    assert manager.get_user_for_burner(first) is None
    assert manager.get_user_for_burner(rotated) == "user-a"

    manager.expire_burner(rotated)
    assert manager.get_user_for_burner(rotated) is None


def test_mock_burner_manager_cleanup_expired_entries():
    manager = MockBurnerManager()
    email = manager.generate_burner_email("user-a")

    manager._burners[email]["expires_at"] = datetime.datetime.now() - datetime.timedelta(seconds=1)
    removed = manager.cleanup_expired()

    assert removed == 1
    assert manager.get_user_for_burner(email) is None
