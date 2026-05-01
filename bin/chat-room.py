#!/usr/bin/env python3
"""
OpSecChat chat-room launcher.

This keeps the repository root flat while the implementation lives under
``src/python``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_python = repo_root / "src" / "python"
    src_python_str = str(src_python)
    if src_python_str not in sys.path:
        sys.path.insert(0, src_python_str)


_bootstrap_import_path()

from chat_room import main


if __name__ == "__main__":
    main()
