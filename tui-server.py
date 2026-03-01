#!/usr/bin/env python3
"""
OpSecChat TUI Server Launcher

Launches the TUI-based chat server with optional Tor integration.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tui.server import main

if __name__ == '__main__':
    main()
