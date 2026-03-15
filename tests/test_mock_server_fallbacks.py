import datetime
import unittest

from mock_email_fallbacks import MockBurnerManager, MockEmailStorage


class TestMockEmailStorage(unittest.TestCase):
    def test_creates_and_reads_inboxes(self):
        storage = MockEmailStorage()

        storage.create_user_inbox("user-a")
        storage.add_email("user-a", {"subject": "hello"})

        inbox = storage.get_user_inbox("user-a")
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["subject"], "hello")


class TestMockBurnerManager(unittest.TestCase):
    def test_generate_rotate_and_expire(self):
        manager = MockBurnerManager()

        first = manager.generate_burner_email("user-a")
        self.assertEqual(manager.get_user_for_burner(first), "user-a")
        self.assertIn(first, manager.get_user_burners("user-a"))

        rotated = manager.rotate_burner("user-a", first)
        self.assertNotEqual(rotated, first)
        self.assertIsNone(manager.get_user_for_burner(first))
        self.assertEqual(manager.get_user_for_burner(rotated), "user-a")

        manager.expire_burner(rotated)
        self.assertIsNone(manager.get_user_for_burner(rotated))

    def test_cleanup_expired_entries(self):
        manager = MockBurnerManager()
        email = manager.generate_burner_email("user-a")

        manager._burners[email]["expires_at"] = datetime.datetime.now() - datetime.timedelta(seconds=1)
        removed = manager.cleanup_expired()

        self.assertEqual(removed, 1)
        self.assertIsNone(manager.get_user_for_burner(email))


if __name__ == "__main__":
    unittest.main()
