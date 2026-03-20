"""
Tests for key management UI routes.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


class TestKeyManagementRoutes:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_keys_page_is_available(self):
        response = self.client.get("/keys")
        assert response.status_code == 200
        assert b"Key Management" in response.data

    def test_keys_page_uses_external_scripts_only(self):
        html = self.client.get("/keys").get_data(as_text=True)

        # No inline <script> blocks.
        assert re.search(r"<script(?![^>]*\\bsrc=)", html) is None
        # Avoid inline script attributes on elements.
        assert re.search(r"\\son[a-zA-Z]+\\s*=", html) is None

    def test_keys_page_includes_expected_assets(self):
        html = self.client.get("/keys").get_data(as_text=True)
        assert "openpgp.min.js" in html
        assert "pgp-manager.js" in html
        assert "key-management.js" in html
        assert "key-management.css" in html
