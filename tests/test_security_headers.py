"""
Tests for CSP mode resolution and security header behavior.
"""

from app_factory import create_app
from security_headers import (
    build_csp_header,
    detect_template_inline_usage,
    resolve_csp_mode,
)


def test_detect_template_inline_usage_flags_expected_patterns(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "safe.html").write_text(
        "<html><head><script src='/static/app.js'></script></head></html>",
        encoding="utf-8",
    )
    (templates_dir / "inline.html").write_text(
        "<html><body style='color: red'><script>console.log('inline')</script></body></html>",
        encoding="utf-8",
    )
    (templates_dir / "event.html").write_text(
        "<button onclick='doThing()'>Run</button>",
        encoding="utf-8",
    )

    results = detect_template_inline_usage(str(templates_dir))

    assert results["files_scanned"] == 3
    assert results["has_inline_script"] is True
    assert results["has_style_attribute"] is True
    assert results["has_inline_event_handler"] is True


def test_resolve_csp_mode_auto_uses_compatible_with_inline_patterns():
    resolved = resolve_csp_mode(
        "auto",
        {
            "has_inline_script": True,
            "has_style_attribute": False,
            "has_inline_event_handler": False,
            "files_scanned": 4,
        },
    )
    assert resolved == "compatible"


def test_resolve_csp_mode_auto_uses_strict_when_no_inline_patterns():
    resolved = resolve_csp_mode(
        "auto",
        {
            "has_inline_script": False,
            "has_style_attribute": False,
            "has_inline_event_handler": False,
            "files_scanned": 4,
        },
    )
    assert resolved == "strict"


def test_build_csp_header_strict_disallows_unsafe_inline():
    csp = build_csp_header("strict")
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "'unsafe-inline'" not in csp


def test_build_csp_header_compatible_allows_unsafe_inline():
    csp = build_csp_header("compatible")
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_app_defaults_to_auto_mode_and_compatible_csp(monkeypatch):
    monkeypatch.delenv("OPSECHAT_CSP_MODE", raising=False)
    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    csp = response.headers.get("Content-Security-Policy", "")
    assert response.status_code == 200
    assert app.config["SECURITY_HEADERS_CSP_MODE_CONFIGURED"] == "auto"
    assert app.config["SECURITY_HEADERS_CSP_MODE_EFFECTIVE"] == "compatible"
    assert "'unsafe-inline'" in csp
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_app_honors_strict_csp_override(monkeypatch):
    monkeypatch.setenv("OPSECHAT_CSP_MODE", "strict")
    app = create_app()
    client = app.test_client()
    response = client.get("/health")

    csp = response.headers.get("Content-Security-Policy", "")
    assert response.status_code == 200
    assert app.config["SECURITY_HEADERS_CSP_MODE_CONFIGURED"] == "strict"
    assert app.config["SECURITY_HEADERS_CSP_MODE_EFFECTIVE"] == "strict"
    assert "'unsafe-inline'" not in csp
