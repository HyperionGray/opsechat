"""
Policy routes for legal document display.

Provides public routes for:
- /terms
- /aup
- /privacy
- /policies

The route layer renders markdown policy documents into sanitized HTML with a
small built-in renderer to avoid adding runtime dependencies.
"""

from __future__ import annotations

import html
import os
import re
from typing import Dict, List, Tuple

from flask import render_template

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_POLICY_FILES = {
    "terms": {
        "title": "Terms of Service",
        "path": os.path.join(_BASE_DIR, "docs", "legal", "TERMS_OF_SERVICE.md"),
        "route": "/terms",
    },
    "aup": {
        "title": "Acceptable Use Policy",
        "path": os.path.join(_BASE_DIR, "docs", "legal", "ACCEPTABLE_USE_POLICY.md"),
        "route": "/aup",
    },
    "privacy": {
        "title": "Privacy Policy",
        "path": os.path.join(_BASE_DIR, "docs", "legal", "PRIVACY_POLICY.md"),
        "route": "/privacy",
    },
}

_POLICY_CACHE: Dict[str, Dict[str, object]] = {}


def _load_version() -> str:
    """Read app version from VERSION with a safe fallback."""
    try:
        with open(os.path.join(_BASE_DIR, "VERSION"), "r", encoding="utf-8") as version_file:
            return version_file.read().strip() or "0.8.0-alpha"
    except (FileNotFoundError, OSError):
        return "0.8.0-alpha"


def _extract_last_updated(markdown_text: str) -> str:
    """Extract 'Last Updated' metadata when present."""
    match = re.search(r"\*\*Last Updated:\*\*\s*(.+)", markdown_text)
    if match:
        return match.group(1).strip()
    return "Unspecified"


def _slugify_heading(text: str, seen: Dict[str, int]) -> str:
    """Create deterministic heading IDs for table-of-contents anchors."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "section"
    seen[slug] = seen.get(slug, 0) + 1
    if seen[slug] > 1:
        return f"{slug}-{seen[slug]}"
    return slug


def _render_inline(text: str) -> str:
    """Render inline markdown safely (links + code + plain text)."""
    escaped = html.escape(text)

    # Inline code: `value`
    escaped = re.sub(
        r"`([^`]+)`",
        lambda m: f"<code>{m.group(1)}</code>",
        escaped,
    )

    # Links: [text](url)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: (
            f'<a href="{_safe_href(m.group(2))}" '
            f'rel="noopener noreferrer">{m.group(1)}</a>'
        ),
        escaped,
    )

    return escaped


def _safe_href(href: str) -> str:
    """Allow only safe URL schemes in rendered markdown links."""
    normalized = href.strip().lower()
    policy_aliases = {
        "terms_of_service.md": "/terms",
        "acceptable_use_policy.md": "/aup",
        "privacy_policy.md": "/privacy",
        "docs/legal/terms_of_service.md": "/terms",
        "docs/legal/acceptable_use_policy.md": "/aup",
        "docs/legal/privacy_policy.md": "/privacy",
    }
    if normalized in policy_aliases:
        return policy_aliases[normalized]

    if normalized.startswith(("http://", "https://", "/", "#", "mailto:")):
        return html.escape(href.strip(), quote=True)
    if re.fullmatch(r"[a-z0-9._/-]+", normalized):
        return html.escape(href.strip(), quote=True)
    return "#"


def _render_markdown(markdown_text: str) -> Tuple[str, List[Dict[str, object]]]:
    """
    Render markdown as safe HTML.

    Supported constructs:
    - Headings (# ... ######)
    - Bullet lists (- item / * item)
    - Horizontal rule (---)
    - Fenced code blocks (```)
    - Paragraphs
    - Inline code and markdown links
    """
    lines = markdown_text.splitlines()
    html_lines: List[str] = []
    toc: List[Dict[str, object]] = []
    heading_ids: Dict[str, int] = {}
    in_list = False
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if not in_code_block:
                html_lines.append("<pre><code>")
                in_code_block = True
            else:
                html_lines.append("</code></pre>")
                in_code_block = False
            continue

        if in_code_block:
            html_lines.append(html.escape(line))
            continue

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

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            anchor = _slugify_heading(title, heading_ids)
            toc.append({"level": level, "title": title, "anchor": anchor})
            html_lines.append(f'<h{level} id="{anchor}">{_render_inline(title)}</h{level}>')
            continue

        list_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if list_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_render_inline(list_match.group(1).strip())}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{_render_inline(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code_block:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines), toc


def _load_policy(policy_key: str) -> Dict[str, object]:
    """Read and render one policy doc with in-memory mtime cache."""
    policy = _POLICY_FILES[policy_key]
    source_path = policy["path"]

    try:
        mtime = os.path.getmtime(source_path)
    except OSError:
        mtime = None

    cached = _POLICY_CACHE.get(policy_key)
    if cached and cached.get("mtime") == mtime:
        return cached

    if mtime is None:
        rendered = {
            "title": policy["title"],
            "route": policy["route"],
            "last_updated": "Unavailable",
            "html": "<p>This policy document is currently unavailable.</p>",
            "toc": [],
            "mtime": None,
        }
        _POLICY_CACHE[policy_key] = rendered
        return rendered

    with open(source_path, "r", encoding="utf-8") as policy_file:
        markdown_text = policy_file.read()

    html_content, toc = _render_markdown(markdown_text)
    rendered = {
        "title": policy["title"],
        "route": policy["route"],
        "last_updated": _extract_last_updated(markdown_text),
        "html": html_content,
        "toc": toc,
        "mtime": mtime,
    }
    _POLICY_CACHE[policy_key] = rendered
    return rendered


def register_policy_routes(app):
    """Register legal policy pages."""
    def _all_policies() -> List[Dict[str, object]]:
        return [_load_policy("terms"), _load_policy("aup"), _load_policy("privacy")]

    @app.route("/terms", methods=["GET"])
    def terms_page():
        policy = _load_policy("terms")
        return render_template(
            "policy_page.html",
            policy=policy,
            all_policies=_all_policies(),
            version=_load_version(),
        )

    @app.route("/aup", methods=["GET"])
    def aup_page():
        policy = _load_policy("aup")
        return render_template(
            "policy_page.html",
            policy=policy,
            all_policies=_all_policies(),
            version=_load_version(),
        )

    @app.route("/privacy", methods=["GET"])
    def privacy_page():
        policy = _load_policy("privacy")
        return render_template(
            "policy_page.html",
            policy=policy,
            all_policies=_all_policies(),
            version=_load_version(),
        )

    @app.route("/policies", methods=["GET"])
    def policies_index():
        return render_template(
            "policies.html",
            policies=_all_policies(),
            version=_load_version(),
        )
