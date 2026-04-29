#!/usr/bin/env python3
"""
Start the real Flask application for Playwright smoke tests.

This bypasses the legacy mock server so browser automation can exercise the
closed-roster OpenPGP room implementation directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_factory import create_app


def main() -> None:
    port = int(os.environ.get("OPSECHAT_PLAYWRIGHT_PORT", "5111"))
    app = create_app()
    app.config["TESTING"] = True
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
