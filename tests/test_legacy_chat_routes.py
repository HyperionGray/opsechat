"""
Regression tests for legacy chat routes/templates.

These endpoints back the original drop.html frontend and use form-encoded
payloads (`dropdata`) plus `/chatsjs` polling.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _legacy_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "legacy-path-123"
    app.config["hostname"] = "localhost"
    return app.test_client()


class TestLegacyChatRoutes:
    def setup_method(self):
        self.client = _legacy_client()

    def test_yesscript_route_renders_drop_template(self):
        resp = self.client.get("/legacy-path-123/yesscript")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "id=\"messagearea\"" in body

    def test_chatsjs_accepts_form_encoded_dropdata(self):
        post_resp = self.client.post(
            "/legacy-path-123/chatsjs",
            data={"dropdata": "legacy hello"},
        )
        assert post_resp.status_code == 200

        get_resp = self.client.get("/legacy-path-123/chatsjs")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert isinstance(data, list)
        assert any(msg.get("msg") == "legacy hello" for msg in data)

    def test_chats_route_renders_messages_html(self):
        self.client.post("/legacy-path-123/chats", data={"dropdata": "html hello"})
        resp = self.client.get("/legacy-path-123/chats")
        assert resp.status_code == 200
        assert "html hello" in resp.get_data(as_text=True)
