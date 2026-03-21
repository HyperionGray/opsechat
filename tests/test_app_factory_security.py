import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app


def _build_client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "pytest-secret"
    app.config["path"] = "secpath"
    app.config["hostname"] = "localhost"
    return app.test_client()


def test_csp_header_contains_nonce_without_unsafe_inline():
    client = _build_client()
    response = client.get("/secpath/mail")
    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self' 'nonce-" in csp
    assert "style-src 'self' 'nonce-" in csp
    assert "unsafe-inline" not in csp


def test_html_includes_script_and_style_nonce_matching_header():
    client = _build_client()
    response = client.get("/secpath/mail")
    csp = response.headers["Content-Security-Policy"]
    nonce_match = re.search(r"'nonce-([^']+)'", csp)
    assert nonce_match is not None
    nonce = nonce_match.group(1)

    html = response.get_data(as_text=True)
    assert f'<script nonce="{nonce}"' in html
    assert f'<style nonce="{nonce}"' in html
