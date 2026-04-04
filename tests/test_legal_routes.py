"""
Tests for legal policy routes and markdown rendering.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app
import legal_routes


def _fresh_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestLegalRoutes:
    def setup_method(self):
        self.client = _fresh_client()

    def test_terms_route_returns_200(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        assert "Terms of Service" in response.data.decode()

    def test_aup_route_returns_200(self):
        response = self.client.get("/aup")
        assert response.status_code == 200
        assert "Acceptable Use Policy" in response.data.decode()

    def test_privacy_route_returns_200(self):
        response = self.client.get("/privacy")
        assert response.status_code == 200
        assert "Privacy Policy" in response.data.decode()

    def test_terms_trailing_slash_supported(self):
        response = self.client.get("/terms/")
        assert response.status_code == 200

    def test_internal_markdown_links_are_mapped_to_routes(self):
        response = self.client.get("/terms")
        body = response.data.decode()
        assert 'href="/privacy"' in body
        assert 'href="/aup"' in body

    def test_external_links_open_in_new_tab_safely(self):
        rendered = legal_routes._render_inline("[x](https://example.com)")
        assert 'target="_blank"' in rendered
        assert 'rel="noopener noreferrer"' in rendered

    def test_disallow_javascript_url_scheme_in_links(self):
        rendered = legal_routes._render_inline("[x](javascript:alert(1))")
        assert 'href="#"' in rendered
