#!/usr/bin/env python3
"""
Unit tests for TUI server core behavior.
"""

import time
import unittest

from src.tui.server import ChatServer


class TestTuiServer(unittest.TestCase):
    def test_message_lifetime_is_four_minutes(self):
        """Messages should burn after 4 minutes (240s)."""
        server = ChatServer()
        self.assertEqual(server.MESSAGE_LIFETIME, 240)

    def test_add_message_sanitizes_and_returns_clean_content(self):
        """Messages are sanitized before storing/broadcasting."""
        server = ChatServer()
        accepted, payload = server.add_message("UserA", " <b>Hello & welcome</b> ")
        self.assertTrue(accepted)
        self.assertEqual(payload, "bHello  welcome/b")
        stored = server.get_messages()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["message"], "bHello  welcome/b")

    def test_add_message_rejects_probable_base64_payload(self):
        """Large base64-like payloads should be rejected."""
        server = ChatServer()
        suspicious = "A" * 600
        accepted, error = server.add_message("UserA", suspicious)
        self.assertFalse(accepted)
        self.assertIn("encoded/binary", error)

    def test_per_client_rate_limit_blocks_and_recovers(self):
        """A client should be throttled after exceeding configured threshold."""
        server = ChatServer(rate_limit_messages=2, rate_limit_window_seconds=1)
        client_id = object()

        allowed_1, retry_after_1 = server._check_and_record_rate_limit(client_id)
        allowed_2, retry_after_2 = server._check_and_record_rate_limit(client_id)
        allowed_3, retry_after_3 = server._check_and_record_rate_limit(client_id)

        self.assertTrue(allowed_1)
        self.assertEqual(retry_after_1, 0)
        self.assertTrue(allowed_2)
        self.assertEqual(retry_after_2, 0)
        self.assertFalse(allowed_3)
        self.assertGreaterEqual(retry_after_3, 1)

        time.sleep(1.1)
        allowed_4, retry_after_4 = server._check_and_record_rate_limit(client_id)
        self.assertTrue(allowed_4)
        self.assertEqual(retry_after_4, 0)

    def test_rate_limit_is_per_client_not_global(self):
        """One noisy client should not throttle another client."""
        server = ChatServer(rate_limit_messages=1, rate_limit_window_seconds=10)
        client_a = object()
        client_b = object()

        self.assertTrue(server._check_and_record_rate_limit(client_a)[0])
        self.assertFalse(server._check_and_record_rate_limit(client_a)[0])
        self.assertTrue(server._check_and_record_rate_limit(client_b)[0])


if __name__ == "__main__":
    unittest.main()
