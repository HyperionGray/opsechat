"""
Legal and policy page routes for opsechat.

This module renders markdown policy files (Terms, AUP, Privacy) to safe HTML
without requiring third-party markdown dependencies.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from flask import abort, render_template


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DOCS_LEGAL_DIR = os.path.join(_BASE_DIR, "docs", "legal")

_POLICIES = {
    "terms": {
        "title": "Terms of Service",
        "path": os.path.join(_DOCS_LEGAL_DIR, "TERMS_OF_SERVICE.md"),
        "description": "Terms governing use of opsechat.",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "path": os.path.join(_DOCS_LEGAL_DIR, "ACCEPTABLE_USE_POLICY.md"),
        "description": "Rules for lawful, ethical service usage.",
    },
    "privacy": {
        "title": "Privacy Policy",
        "path": os.path.join(_DOCS_LEGAL_DIR, "PRIVACY_POLICY.md"),
        "description": "How opsechat handles data and metadata.",
    },
}

# path -> {mtime, html, toc, last_updated}
_POLICY_CACHE: Dict[str, Dict[str, object]] = {}

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_BULLET_RE = re.compile(r"^(\s*)-\s+(.*)$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _normalize_href(raw_href: str) -> str:
    href = raw_href.strip()
    lowered = href.lower()
    if lowered in ("privacy_policy.md", "./privacy_policy.md"):
        return "/privacy"
    if lowered in ("acceptable_use_policy.md", "./acceptable_use_policy.md"):
        return "/aup"
    if lowered in ("terms_of_service.md", "./terms_of_service.md"):
        return "/terms"
    if lowered.endswith("/privacy_policy.md"):
        return "/privacy"
    if lowered.endswith("/acceptable_use_policy.md"):
        return "/aup"
    if lowered.endswith("/terms_of_service.md"):
        return "/terms"
    if lowered.startswith(("http://", "https://", "mailto:", "/", "#")):
        return href
    return "#"


def _format_emphasis(text: str) -> str:
    escaped = html.escape(text)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_RE.sub(r"<em>\1</em>", escaped)
    return escaped


def _format_inline(text: str) -> str:
    chunks: List[str] = []
    last = 0
    for match in _LINK_RE.finditer(text):
        chunks.append(_format_emphasis(text[last:match.start()]))
        label = html.escape(match.group(1).strip())
        href = html.escape(_normalize_href(match.group(2)))
        chunks.append(f'<a href="{href}">{label}</a>')
        last = match.end()
    chunks.append(_format_emphasis(text[last:]))
    return "".join(chunks)


def _render_markdown(md_text: str) -> Tuple[str, List[Dict[str, object]]]:
    html_lines: List[str] = []
    toc: List[Dict[str, object]] = []
    in_list = False
    slug_counts: Dict[str, int] = {}

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if stripped == "---":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
            continue

        if stripped.startswith("#"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = min(6, len(stripped) - len(stripped.lstrip("#")))
            heading_text = stripped[level:].strip()
            heading_id = _slugify(heading_text)
            seen = slug_counts.get(heading_id, 0)
            slug_counts[heading_id] = seen + 1
            if seen:
                heading_id = f"{heading_id}-{seen + 1}"
            html_lines.append(
                f'<h{level} id="{html.escape(heading_id)}">{_format_inline(heading_text)}</h{level}>'
            )
            if level <= 3:
                toc.append({"id": heading_id, "title": heading_text, "level": level})
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_format_inline(bullet.group(2).strip())}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{_format_inline(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines), toc


def _read_policy(policy_key: str) -> Dict[str, object]:
    policy = _POLICIES.get(policy_key)
    if not policy:
        abort(404)

    file_path = policy["path"]
    if not os.path.exists(file_path):
        abort(404)

    mtime = os.path.getmtime(file_path)
    cached = _POLICY_CACHE.get(file_path)
    if cached and cached.get("mtime") == mtime:
        return cached

    with open(file_path, "r", encoding="utf-8") as handle:
        md_text = handle.read()

    rendered_html, toc = _render_markdown(md_text)
    last_updated = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    parsed = {
        "mtime": mtime,
        "html": rendered_html,
        "toc": toc,
        "last_updated": last_updated,
    }
    _POLICY_CACHE[file_path] = parsed
    return parsed


def register_legal_routes(app):
    """Register legal/policy routes on the Flask app."""

    @app.route("/terms")
    def terms():
        parsed = _read_policy("terms")
        return render_template(
            "legal_policy.html",
            policy_key="terms",
            page_title=_POLICIES["terms"]["title"],
            page_description=_POLICIES["terms"]["description"],
            content_html=parsed["html"],
            toc=parsed["toc"],
            updated_at=parsed["last_updated"],
        )

    @app.route("/aup")
    def aup():
        parsed = _read_policy("aup")
        return render_template(
            "legal_policy.html",
            policy_key="aup",
            page_title=_POLICIES["aup"]["title"],
            page_description=_POLICIES["aup"]["description"],
            content_html=parsed["html"],
            toc=parsed["toc"],
            updated_at=parsed["last_updated"],
        )

    @app.route("/privacy")
    def privacy():
        parsed = _read_policy("privacy")
        return render_template(
            "legal_policy.html",
            policy_key="privacy",
            page_title=_POLICIES["privacy"]["title"],
            page_description=_POLICIES["privacy"]["description"],
            content_html=parsed["html"],
            toc=parsed["toc"],
            updated_at=parsed["last_updated"],
        )
