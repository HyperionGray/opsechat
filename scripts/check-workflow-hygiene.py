#!/usr/bin/env python3
"""CLI wrapper for scripts.check_workflow_hygiene."""

import sys
from pathlib import Path

# Ensure repository root is importable when executed as a file path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_workflow_hygiene import main


if __name__ == "__main__":
    raise SystemExit(main())
