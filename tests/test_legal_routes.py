"""
Integration tests for public legal policy pages.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


class TestLegalPages:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_terms_page_renders(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Terms of Service" in body
        assert "Source: docs/legal/TERMS_OF_SERVICE.md" in body

    def test_aup_page_renders(self):
        response = self.client.get("/aup")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Acceptable Use Policy" in body
        assert "Source: docs/legal/ACCEPTABLE_USE_POLICY.md" in body

    def test_privacy_page_renders(self):
        response = self.client.get("/privacy")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Privacy Policy" in body
        assert "Source: docs/legal/PRIVACY_POLICY.md" in body

    def test_legal_page_nav_links_present(self):
        response = self.client.get("/privacy")
        body = response.get_data(as_text=True)
        assert 'href="/terms"' in body
        assert 'href="/aup"' in body
        assert 'href="/privacy"' in body
