"""
Tests for CSP nonce generation and template propagation.
"""

import re

from app_factory import create_app


SCRIPT_NONCE_PATTERN = re.compile(r"script-src 'self' 'nonce-([^']+)'")


def _extract_script_nonce(csp_header: str) -> str:
    """Extract nonce value from the script-src directive."""
    match = SCRIPT_NONCE_PATTERN.search(csp_header or "")
    assert match is not None, f"Missing script nonce in CSP header: {csp_header!r}"
    return match.group(1)


def test_chat_page_csp_nonce_is_present_and_applied_to_script_tags():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response = client.get("/chat")

    assert response.status_code == 200
    csp_header = response.headers.get("Content-Security-Policy", "")
    nonce = _extract_script_nonce(csp_header)

    html = response.get_data(as_text=True)
    assert f'nonce="{nonce}"' in html
    assert "<script" in html


def test_csp_nonce_changes_per_request():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        response_a = client.get("/chat")
        response_b = client.get("/chat")

    nonce_a = _extract_script_nonce(response_a.headers.get("Content-Security-Policy", ""))
    nonce_b = _extract_script_nonce(response_b.headers.get("Content-Security-Policy", ""))

    assert nonce_a != nonce_b
