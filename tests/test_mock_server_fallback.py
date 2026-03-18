#!/usr/bin/env python3
"""Unit tests for mock server in-memory fallback backends."""

import datetime

from tests.mock_server import InMemoryMockBurnerManager, InMemoryMockEmailStorage


def test_in_memory_mock_email_storage_round_trip():
    storage = InMemoryMockEmailStorage()
    user_id = "user-123"

    storage.create_user_inbox(user_id)
    storage.add_email(user_id, {"subject": "hello", "body": "world"})

    emails = storage.get_emails(user_id)
    assert len(emails) == 1
    assert emails[0]["subject"] == "hello"
    assert "timestamp" in emails[0]


def test_in_memory_mock_burner_lifecycle():
    manager = InMemoryMockBurnerManager(domain="test.local", hours_valid=1)
    user_id = "user-abc"

    burner = manager.generate_burner_email(user_id)
    assert burner.endswith("@test.local")
    assert manager.get_user_for_burner(burner) == user_id
    assert len(manager.get_user_burners(user_id)) == 1

    rotated = manager.rotate_burner(user_id, old_email=burner)
    assert rotated != burner
    assert manager.get_user_for_burner(burner) is None
    assert manager.get_user_for_burner(rotated) == user_id
    assert manager.expire_burner(rotated) is True
    assert manager.get_user_for_burner(rotated) is None


def test_in_memory_mock_burner_cleanup_removes_expired():
    manager = InMemoryMockBurnerManager(domain="test.local", hours_valid=1)
    user_id = "user-cleanup"
    burner = manager.generate_burner_email(user_id)

    manager.burners[burner]["expires_at"] = datetime.datetime.now() - datetime.timedelta(seconds=1)
    manager.cleanup_expired()

    assert manager.get_user_for_burner(burner) is None
    assert manager.get_user_burners(user_id) == []
