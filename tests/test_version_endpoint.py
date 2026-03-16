#!/usr/bin/env python3
"""
Unit tests for the /version endpoint.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app_factory import create_app


class TestVersionEndpoint(unittest.TestCase):
    """Validate version route behavior."""

    def setUp(self):
        self.client = create_app().test_client()
        with open(os.path.join(REPO_ROOT, "VERSION")) as f:
            self.expected_version = f.read().strip()

    def test_version_endpoint_returns_200(self):
        response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)

    def test_version_endpoint_returns_expected_payload(self):
        response = self.client.get("/version")
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("version"), self.expected_version)


if __name__ == "__main__":
    unittest.main()
