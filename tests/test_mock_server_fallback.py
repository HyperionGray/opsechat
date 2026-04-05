"""
Tests for the mock-server fallback email/burner implementation.
"""

import datetime
import ast
import random
import string
import unittest
from pathlib import Path
from typing import Dict, List, Optional


def _load_fallback_classes():
    """
    Load only fallback class definitions from mock_server.py without importing
    Flask or executing app initialization side effects.
    """
    tests_dir = Path(__file__).resolve().parent
    mock_server_path = tests_dir / "mock_server.py"
    source = mock_server_path.read_text(encoding="utf-8")
    parsed = ast.parse(source)

    selected_nodes = []
    for node in parsed.body:
        if isinstance(node, ast.FunctionDef) and node.name == "id_generator":
            selected_nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name in {
            "InMemoryMockEmailStorage",
            "InMemoryMockBurnerManager",
        }:
            selected_nodes.append(node)

    module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {
        "datetime": datetime,
        "random": random,
        "string": string,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
    }
    exec(compile(module, str(mock_server_path), "exec"), namespace)
    return namespace["InMemoryMockEmailStorage"], namespace["InMemoryMockBurnerManager"]


class TestMockServerFallback(unittest.TestCase):
    def test_in_memory_email_storage_supports_basic_inbox_flow(self):
        storage_cls, _ = _load_fallback_classes()
        storage = storage_cls()

        storage.create_user_inbox("alice")
        storage.add_email(
            "alice",
            {
                "from": "sender@example.com",
                "to": "alice@example.com",
                "subject": "hello",
                "body": "body text",
            },
        )

        messages = storage.get_emails("alice")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["subject"], "hello")
        self.assertIn("id", messages[0])
        self.assertIn("timestamp", messages[0])

    def test_in_memory_burner_manager_full_lifecycle(self):
        storage_cls, burner_cls = _load_fallback_classes()
        storage = storage_cls()
        manager = burner_cls(storage)

        email = manager.generate_burner_email("alice")
        self.assertEqual(manager.get_user_for_burner(email), "alice")
        self.assertTrue(any(entry["email"] == email for entry in manager.get_user_burners("alice")))

        rotated = manager.rotate_burner("alice", old_email=email)
        self.assertNotEqual(rotated, email)
        self.assertIsNone(manager.get_user_for_burner(email))
        self.assertEqual(manager.get_user_for_burner(rotated), "alice")

        self.assertTrue(manager.expire_burner(rotated))
        self.assertFalse(manager.expire_burner(rotated))
        self.assertIsNone(manager.get_user_for_burner(rotated))

    def test_cleanup_expired_burners_removes_user_mapping(self):
        storage_cls, burner_cls = _load_fallback_classes()
        storage = storage_cls()
        manager = burner_cls(storage)

        expired_email = manager.generate_burner_email("bob", hours_valid=1)
        manager.burner_addresses[expired_email]["expires_at"] = (
            datetime.datetime.now() - datetime.timedelta(minutes=1)
        )

        manager.cleanup_expired()

        self.assertNotIn(expired_email, manager.burner_addresses)
        self.assertEqual(manager.get_user_burners("bob"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
