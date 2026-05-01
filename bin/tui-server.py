#!/usr/bin/env python3
"""
OpSecChat TUI Server Launcher

Launches the TUI-based chat server with optional Tor integration.
"""

import sys
from pathlib import Path

SRC_PYTHON = Path(__file__).resolve().parents[1] / "src" / "python"
sys.path.insert(0, str(SRC_PYTHON))

from tui.server import main

if __name__ == '__main__':
    main()
