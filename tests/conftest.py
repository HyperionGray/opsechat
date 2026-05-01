"""Pytest path bootstrap for the reorganized source tree."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = REPO_ROOT / "src" / "python"

src_python_str = str(SRC_PYTHON)
if src_python_str not in sys.path:
    sys.path.insert(0, src_python_str)
