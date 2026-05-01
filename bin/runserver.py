#!/usr/bin/env python3
"""Launch the main OpSecChat web runtime from the organized source tree."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_python = repo_root / "src" / "python"
    src_python_str = str(src_python)
    if src_python_str not in sys.path:
        sys.path.insert(0, src_python_str)
    runpy.run_module("runserver", run_name="__main__")


if __name__ == "__main__":
    main()
