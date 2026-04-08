#!/usr/bin/env python3
"""
PF Task: Run repository hygiene checks.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when hygiene findings exist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output hygiene findings as JSON",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    command = [sys.executable, str(project_root / "scripts" / "repo_hygiene_check.py")]
    if args.strict:
        command.append("--strict")
    if args.json:
        command.append("--json")

    print("=== PF Task: Hygiene ===")
    print(f"[*] Running: {' '.join(command)}")
    completed = subprocess.run(command, cwd=project_root)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
