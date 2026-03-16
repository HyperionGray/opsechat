#!/usr/bin/env python3
"""
Compatibility entrypoint.

This file intentionally delegates to runserver.py to avoid maintaining duplicate
startup logic in two separate modules.
"""

from runserver import app, main, setup_tor_configuration  # noqa: F401
from utils import id_generator, check_older_than, process_chat  # noqa: F401


if __name__ == "__main__":
    main()