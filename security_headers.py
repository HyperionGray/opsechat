"""
Security header configuration helpers.

This module centralizes response hardening headers and manages Content Security
Policy (CSP) behavior using a small mode system:

- strict: no inline scripts/styles allowed
- compatible: allows inline scripts/styles for legacy templates
- auto: detects template usage and selects strict or compatible automatically
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict


logger = logging.getLogger(__name__)

_ALLOWED_CSP_MODES = {"auto", "strict", "compatible"}
_INLINE_SCRIPT_PATTERN = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.IGNORECASE)
_STYLE_ATTR_PATTERN = re.compile(r"\sstyle\s*=", re.IGNORECASE)
_INLINE_EVENT_HANDLER_PATTERN = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def normalize_csp_mode(mode: str | None) -> str:
    """Normalize user configuration into a supported CSP mode."""
    if not mode:
        return "auto"

    normalized = mode.strip().lower()
    if normalized in _ALLOWED_CSP_MODES:
        return normalized
    return "auto"


def detect_template_inline_usage(template_dir: str | None) -> Dict[str, bool | int]:
    """
    Scan template files for inline script/style usage.

    Returns a dictionary with detection flags and a file scan count.
    """
    result: Dict[str, bool | int] = {
        "has_inline_script": False,
        "has_style_attribute": False,
        "has_inline_event_handler": False,
        "files_scanned": 0,
    }

    if not template_dir:
        return result

    template_path = Path(template_dir)
    if not template_path.exists() or not template_path.is_dir():
        return result

    for file_path in template_path.rglob("*.html"):
        try:
            contents = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        result["files_scanned"] = int(result["files_scanned"]) + 1
        if _INLINE_SCRIPT_PATTERN.search(contents):
            result["has_inline_script"] = True
        if _STYLE_ATTR_PATTERN.search(contents):
            result["has_style_attribute"] = True
        if _INLINE_EVENT_HANDLER_PATTERN.search(contents):
            result["has_inline_event_handler"] = True

    return result


def resolve_csp_mode(configured_mode: str | None, template_risks: Dict[str, bool | int]) -> str:
    """Resolve effective CSP mode from configuration and detected template usage."""
    mode = normalize_csp_mode(configured_mode)
    if mode != "auto":
        return mode

    if (
        template_risks.get("has_inline_script")
        or template_risks.get("has_style_attribute")
        or template_risks.get("has_inline_event_handler")
    ):
        return "compatible"

    return "strict"


def build_csp_header(mode: str) -> str:
    """Build a CSP header string for the provided mode."""
    normalized_mode = normalize_csp_mode(mode)
    if normalized_mode == "compatible":
        script_src = "script-src 'self' 'unsafe-inline'"
        style_src = "style-src 'self' 'unsafe-inline'"
    else:
        script_src = "script-src 'self'"
        style_src = "style-src 'self'"

    directives = [
        "default-src 'self'",
        script_src,
        style_src,
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(directives) + ";"


def configure_security_headers(app) -> None:
    """Configure and attach hardening headers to all application responses."""
    configured_mode = normalize_csp_mode(os.getenv("OPSECHAT_CSP_MODE", "auto"))
    template_risks = detect_template_inline_usage(app.template_folder)
    effective_mode = resolve_csp_mode(configured_mode, template_risks)
    csp_header = build_csp_header(effective_mode)

    app.config["SECURITY_HEADERS_CSP_MODE_CONFIGURED"] = configured_mode
    app.config["SECURITY_HEADERS_CSP_MODE_EFFECTIVE"] = effective_mode
    app.config["SECURITY_HEADERS_TEMPLATE_SCAN"] = template_risks

    if configured_mode == "auto" and effective_mode == "compatible":
        logger.warning(
            "CSP auto mode selected 'compatible' due to inline template usage: %s",
            template_risks,
        )

    @app.after_request
    def add_security_headers(response):
        response.headers["Server"] = ""
        response.headers["Date"] = ""
        response.headers["Content-Security-Policy"] = csp_header
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
