from __future__ import annotations

import hashlib
import mmap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from .config import BlobConfig, DEFAULT_BLOB_SEED, DEFAULT_BLOB_SIZE, DEFAULT_WINDOW_SIZE


def _hash_bytes(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=8).hexdigest()


@dataclass
class WindowMatch:
    offset: int
    length: int


class VirtualBlob:
    """Deterministic blob generator used as the shared dictionary."""

    def __init__(self, size: int = DEFAULT_BLOB_SIZE, seed: int = DEFAULT_BLOB_SEED, path: Path | None = None) -> None:
        self.size = size
        self.seed = seed
        self.path = Path(path) if path else None
        self._data: bytearray | mmap.mmap | None = None
        self._window_indexes: dict[int, Dict[str, List[int]]] = {}
        self._mmap: mmap.mmap | None = None
        self._file_handle = None

    def ensure_loaded(self) -> None:
        if self._data is not None:
            return
        if self.path and self.path.exists():
            file_handle = self.path.open("rb")
            self._file_handle = file_handle
            mm = mmap.mmap(file_handle.fileno(), 0, access=mmap.ACCESS_READ)
            self._mmap = mm
            self._data = mm
            self.size = len(mm)
            return
        rng = hashlib.blake2b(str(self.seed).encode(), digest_size=16)
        chunk = bytearray()
        counter = 0
        while len(chunk) < self.size:
            rng.update(counter.to_bytes(4, "big"))
            chunk.extend(rng.digest())
            counter += 1
        self._data = bytearray(chunk[: self.size])

    def read(self, offset: int, length: int) -> bytes:
        self.ensure_loaded()
        assert self._data is not None
        if length <= 0:
            return b""
        start = offset % self.size
        end = start + length
        if end <= self.size:
            return bytes(self._data[start:end])
        first = bytes(self._data[start:])
        remaining = length - len(first)
        repeats = remaining // self.size
        tail = remaining % self.size
        pieces = [first]
        if repeats:
            pieces.extend(bytes(self._data) for _ in range(repeats))
        if tail:
            pieces.append(bytes(self._data[:tail]))
        return b"".join(pieces)

    def iter_windows(self, window_size: int = DEFAULT_WINDOW_SIZE) -> Iterator[Tuple[int, bytes]]:
        self.ensure_loaded()
        assert self._data is not None
        for offset in range(0, self.size, window_size):
            yield offset, bytes(self._data[offset : offset + window_size])

    def _ensure_index(self, window_size: int) -> Dict[str, List[int]]:
        if window_size in self._window_indexes:
            return self._window_indexes[window_size]
        index: Dict[str, List[int]] = {}
        for offset, chunk in self.iter_windows(window_size):
            digest = _hash_bytes(chunk)
            index.setdefault(digest, []).append(offset)
        self._window_indexes[window_size] = index
        return index

    def lookup(self, data: bytes, window_size: int = DEFAULT_WINDOW_SIZE) -> List[WindowMatch]:
        if not data:
            return []
        if len(data) != window_size:
            return []
        index = self._ensure_index(window_size)
        digest = _hash_bytes(data)
        offsets = index.get(digest, [])
        matches: List[WindowMatch] = []
        for offset in offsets:
            if self.read(offset, window_size) == data:
                matches.append(WindowMatch(offset=offset, length=window_size))
        return matches


def load_blob(config: BlobConfig | None = None) -> VirtualBlob:
    cfg = config or BlobConfig(DEFAULT_BLOB_SIZE, DEFAULT_BLOB_SEED)
    key = (
        str(Path(cfg.path).resolve()) if cfg.path else None,
        cfg.size,
        cfg.seed,
    )
    cached = _BLOB_CACHE.get(key)
    if cached is not None:
        return cached
    blob = VirtualBlob(cfg.size, cfg.seed, cfg.path)
    _BLOB_CACHE[key] = blob
    return blob


_BLOB_CACHE: Dict[Tuple[str | None, int, int], VirtualBlob] = {}
