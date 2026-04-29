#!/usr/bin/env python3
"""
Start the real Flask application for Playwright smoke tests.

This bypasses the legacy mock server so browser automation can exercise the
closed-roster OpenPGP room implementation directly.
"""

from __future__ import annotations

import os
import sys
from werkzeug.serving import WSGIRequestHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app_factory import create_app


def main() -> None:
    port = int(os.environ.get("OPSECHAT_PLAYWRIGHT_PORT", "5111"))
    app = create_app()
    app.config["TESTING"] = True

    class _NoServerHeaderHandler(WSGIRequestHandler):
        server_version = ""
        sys_version = ""

        def version_string(self):
            return ""

        def send_header(self, keyword, value):
            if keyword.lower() in {"server", "date"}:
                return
            super().send_header(keyword, value)

    app.run(
        host="127.0.0.1",
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
        request_handler=_NoServerHeaderHandler,
    )


if __name__ == "__main__":
    main()
