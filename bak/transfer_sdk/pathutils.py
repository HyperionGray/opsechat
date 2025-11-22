from __future__ import annotations

import re
from pathlib import Path

_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(candidate: str | None, fallback: str = "upload.bin") -> str:
    """Collapse user-provided filenames into a safe ASCII representation."""
    if not candidate:
        candidate = fallback
    name = Path(candidate).name  # drop directories
    if not name:
        name = fallback
    cleaned = _SAFE_PATTERN.sub("-", name)
    cleaned = cleaned.strip(".-") or fallback
    return cleaned[:255]


def ensure_unique_path(directory: Path, filename: str) -> Path:
    """Return a path inside *directory* that does not yet exist."""
    directory.mkdir(parents=True, exist_ok=True)
    base = Path(filename).stem or "upload"
    suffix = Path(filename).suffix
    candidate = directory / f"{base}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{base}-{counter}{suffix}"
        counter += 1
    return candidate


def resolve_child_path(root: Path, candidate: str) -> Path:
    """Resolve *candidate* within *root*, raising if traversal is attempted."""
    target = (root / candidate).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise ValueError("attempted path traversal outside allowed directory")
    return target
