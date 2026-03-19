from datetime import datetime, timedelta

from tests.mock_email_fallback import create_fallback_email_services


def test_create_user_inbox_is_idempotent():
    email_storage, _ = create_fallback_email_services()

    inbox_first = email_storage.create_user_inbox("user-123")
    inbox_second = email_storage.create_user_inbox("user-123")

    assert inbox_first is inbox_second
    assert inbox_first == []


def test_burner_lifecycle_generate_rotate_and_expire():
    _, burner_manager = create_fallback_email_services()

    first_email = burner_manager.generate_burner_email("alice")
    assert burner_manager.get_user_for_burner(first_email) == "alice"
    assert first_email in burner_manager.get_user_burners("alice")

    rotated_email = burner_manager.rotate_burner("alice", first_email)
    assert rotated_email != first_email
    assert burner_manager.get_user_for_burner(first_email) is None
    assert burner_manager.get_user_for_burner(rotated_email) == "alice"

    assert burner_manager.expire_burner(rotated_email) is True
    assert burner_manager.get_user_for_burner(rotated_email) is None


def test_cleanup_expired_removes_outdated_burners():
    _, burner_manager = create_fallback_email_services()

    active_email = burner_manager.generate_burner_email("bob")
    expired_email = burner_manager.generate_burner_email("bob")
    burner_manager._burners[expired_email]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

    removed_count = burner_manager.cleanup_expired()

    assert removed_count == 1
    assert burner_manager.get_user_for_burner(expired_email) is None
    assert burner_manager.get_user_for_burner(active_email) == "bob"
