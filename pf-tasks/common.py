#!/usr/bin/env python3
"""
Shared helpers for pf-tasks scripts.
"""

import subprocess
import sys
from typing import Optional, Sequence


def run_command(
    cmd: Sequence[str],
    cwd: Optional[str] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run command with consistent logging and error handling."""
    print(f"[*] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as err:
        print(f"[!] Command failed: {err}")
        if err.stderr:
            print(f"[!] Error: {err.stderr}")
        if check:
            sys.exit(1)
        return err


def detect_first_available_tool(tools: Sequence[str]) -> Optional[str]:
    """Return the first available executable from a candidate list."""
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            return tool
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None
