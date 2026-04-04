"""
Tests for legal policy routes and rendering behavior.
"""

from app_factory import create_app


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    return app


class TestLegalRoutes:
    def setup_method(self):
        self.client = _fresh_app().test_client()

    def test_terms_route_returns_200(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Terms of Service" in body
        assert "Policy navigation" in body

    def test_aup_route_returns_200(self):
        response = self.client.get("/aup")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Acceptable Use Policy" in body
        assert "Policy navigation" in body

    def test_privacy_route_returns_200(self):
        response = self.client.get("/privacy")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Privacy Policy" in body
        assert "Data You Provide" in body

    def test_policy_pages_include_cross_links(self):
        response = self.client.get("/privacy")
        body = response.data.decode()
        assert 'href="/terms"' in body
        assert 'href="/aup"' in body
        assert 'href="/privacy"' in body

    def test_markdown_links_to_policy_docs_are_rewritten(self):
        response = self.client.get("/privacy")
        body = response.data.decode()
        # Source markdown contains TERMS_OF_SERVICE.md and ACCEPTABLE_USE_POLICY.md
        assert 'href="/terms"' in body
        assert 'href="/aup"' in body

    def test_unknown_legal_route_returns_404(self):
        response = self.client.get("/policy-not-found")
        assert response.status_code == 404

    def test_policy_routes_have_security_headers(self):
        response = self.client.get("/terms")
        assert response.status_code == 200
        headers = response.headers
        assert "Content-Security-Policy" in headers
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
