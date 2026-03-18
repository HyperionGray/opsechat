import datetime

from mock_email_backend import MockBurnerManager, MockEmailStorage


def test_create_user_inbox_is_idempotent():
    storage = MockEmailStorage()
    storage.create_user_inbox("user1")
    storage.create_user_inbox("user1")
    assert "user1" in storage.emails
    assert storage.emails["user1"] == []


def test_burner_generate_rotate_and_lookup():
    manager = MockBurnerManager()
    first = manager.generate_burner_email("user1")
    assert manager.get_user_for_burner(first) == "user1"

    second = manager.rotate_burner("user1", first)
    assert second != first
    assert manager.get_user_for_burner(first) is None
    assert manager.get_user_for_burner(second) == "user1"


def test_cleanup_expired_removes_user_mapping():
    manager = MockBurnerManager()
    active = manager.generate_burner_email("user1")
    expired = manager.generate_burner_email("user1")
    manager.burner_addresses[expired]["expires_at"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=1)
    )

    manager.cleanup_expired()

    assert expired not in manager.burner_addresses
    assert manager.get_user_for_burner(active) == "user1"
    burners = manager.get_user_burners("user1")
    assert len(burners) == 1
    assert burners[0]["email"] == active
