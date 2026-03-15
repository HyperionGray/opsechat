"""
Shared helpers for reading application version metadata.
"""

import os


def read_version(default: str = "unknown") -> str:
    """
    Read application version from the repository VERSION file.

    Falls back to `default` if the file cannot be read.
    """
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    try:
        with open(version_file) as f:
            version = f.read().strip()
            return version or default
    except OSError:
        return default
