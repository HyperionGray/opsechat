from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Iterable, List


@dataclass
class FileEntry:
    name: str
    size: int
    modified: float
    is_dir: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _try_manifest_entry(path: Path) -> FileEntry | None:
    """If path is an ff3 manifest, return a virtual FileEntry from its metadata."""
    if not path.suffix.endswith("ff3job"):
        return None
    try:
        data = json.loads(path.read_text())
        name = str(data.get("object_name") or path.stem)
        size = int(data.get("object_size") or 0)
        stat = path.stat()
        return FileEntry(name=name, size=size, modified=stat.st_mtime, is_dir=False)
    except Exception:
        return None


def list_directory(directory: Path) -> List[FileEntry]:
    directory.mkdir(parents=True, exist_ok=True)
    entries: List[FileEntry] = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            v = _try_manifest_entry(path)
            if v is not None:
                entries.append(v)
                continue
        stat = path.stat()
        entries.append(FileEntry(name=path.name, size=stat.st_size, modified=stat.st_mtime, is_dir=path.is_dir()))
    return entries


def serialize_entries(entries: Iterable[FileEntry]) -> List[dict]:
    return [entry.to_dict() for entry in entries]
