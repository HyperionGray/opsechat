import importlib
import os
import sys


def _import_mock_server_with_fallback():
    os.environ["OPSECHAT_FORCE_MOCK_EMAIL_BACKEND"] = "1"
    if "tests.mock_server" in sys.modules:
        del sys.modules["tests.mock_server"]
    return importlib.import_module("tests.mock_server")


def _clear_fallback_env():
    os.environ.pop("OPSECHAT_FORCE_MOCK_EMAIL_BACKEND", None)


def test_forced_fallback_backend_enabled():
    mock_server = _import_mock_server_with_fallback()
    assert mock_server.USING_FALLBACK_EMAIL_BACKEND is True
    _clear_fallback_env()


def test_mock_email_storage_lifecycle():
    mock_server = _import_mock_server_with_fallback()
    storage = mock_server.email_storage

    user_id = "fallback-user"
    storage.create_user_inbox(user_id)
    assert storage.get_emails(user_id) == []

    email_id = storage.add_email(
        user_id,
        {
            "from": "sender@example.com",
            "to": "receiver@example.com",
            "subject": "Hello",
            "body": "Body",
        },
    )
    assert isinstance(email_id, str)
    assert storage.get_email(user_id, email_id)["subject"] == "Hello"

    updated = storage.update_email(
        user_id,
        email_id,
        {
            "from": "sender@example.com",
            "to": "receiver@example.com",
            "subject": "Updated",
            "body": "Updated body",
            "headers": {},
        },
    )
    assert updated is True
    assert storage.get_email(user_id, email_id)["subject"] == "Updated"

    deleted = storage.delete_email(user_id, email_id)
    assert deleted is True
    assert storage.get_email(user_id, email_id) is None
    _clear_fallback_env()


def test_mock_burner_manager_lifecycle():
    mock_server = _import_mock_server_with_fallback()
    manager = mock_server.burner_manager
    user_id = "burner-user"

    burner = manager.generate_burner_email(user_id, domain="example.com", hours_valid=1)
    assert burner.endswith("@example.com")
    assert manager.get_user_for_burner(burner) == user_id
    assert any(item["email"] == burner for item in manager.get_user_burners(user_id))

    rotated = manager.rotate_burner(user_id, old_email=burner)
    assert rotated != burner
    assert manager.get_user_for_burner(burner) is None
    assert manager.get_user_for_burner(rotated) == user_id

    expired = manager.expire_burner(rotated)
    assert expired is True
    assert manager.get_user_for_burner(rotated) is None
    _clear_fallback_env()
