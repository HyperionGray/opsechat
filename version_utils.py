"""
Helpers for reading the application version consistently.
"""

from pathlib import Path


_BASE_DIR = Path(__file__).resolve().parent
_VERSION_FILE = _BASE_DIR / "VERSION"


def read_version(fallback: str = "unknown") -> str:
    """
    Read version text from the repository VERSION file.

    Args:
        fallback: Value returned when VERSION is unavailable.
    """
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback
