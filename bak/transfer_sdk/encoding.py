from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from .blob import VirtualBlob
from .arithmetic import encode_proto
from .config import (
    BlobConfig,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MIN_MATCH,
    DEFAULT_WINDOW_SIZE,
)


@dataclass
class TransferWindow:
    idx: int
    bref: List[Dict[str, int]]
    raw: str | None = None
    proto: str | None = None


@dataclass
class TransferJob:
    object_name: str
    object_size: int
    window_size: int
    total_windows: int
    blob: BlobConfig
    sha256: str
    windows: List[TransferWindow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_chunks(path: Path, window_size: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(window_size)
            if not chunk:
                break
            yield chunk


def _blob_bytes(blob: VirtualBlob, size_hint: Optional[int]) -> bytes:
    """Read the entire blob into memory (once per job)."""
    size = int(size_hint or blob.size)
    return blob.read(0, size)


def _candidate_offsets(index: Dict[bytes, List[int]], key: bytes, blob_data: bytes) -> List[int]:
    """Return up to DEFAULT_MAX_CANDIDATES offsets in blob_data matching key."""
    cached = index.get(key)
    if cached is not None:
        return cached
    offsets: List[int] = []
    start = 0
    while len(offsets) < DEFAULT_MAX_CANDIDATES:
        pos = blob_data.find(key, start)
        if pos < 0:
            break
        offsets.append(pos)
        start = pos + 1
    index[key] = offsets
    return offsets


def _extend(blob_data: bytes, blob_off: int, chunk: bytes, chunk_off: int) -> int:
    """Return the maximum extension length for blob/chunk alignment."""
    b_len = len(blob_data)
    c_len = len(chunk)
    n = 0
    while blob_off + n < b_len and chunk_off + n < c_len:
        if blob_data[blob_off + n] != chunk[chunk_off + n]:
            break
        n += 1
    return n


def _find_runs_for_chunk(
    chunk: bytes,
    blob_data: bytes,
    min_match: int = DEFAULT_MIN_MATCH,
) -> List[Tuple[int, int, int]]:
    """Greedy LZ77-style parse against a static dictionary (the shared blob).

    Returns a list of runs as (chunk_offset, blob_offset, length). Literals are
    not returned here; they will be emitted by encode_proto as literal segments.
    """
    runs: List[Tuple[int, int, int]] = []
    index: Dict[bytes, List[int]] = {}

    i = 0
    end = len(chunk)

    while i < end:
        if i + min_match > end:
            break
        key = chunk[i : i + min_match]
        best_len = 0
        best_blob_off = -1

        for blob_off in _candidate_offsets(index, key, blob_data):
            length = _extend(blob_data, blob_off, chunk, i)
            if length > best_len:
                best_len = length
                best_blob_off = blob_off
            if i + best_len >= end:
                break

        if best_len >= min_match and best_blob_off >= 0:
            if (
                runs
                and runs[-1][0] + runs[-1][2] == i
                and runs[-1][1] + runs[-1][2] == best_blob_off
            ):
                prev = runs[-1]
                runs[-1] = (prev[0], prev[1], prev[2] + best_len)
            else:
                runs.append((i, best_blob_off, best_len))
            i += best_len
        else:
            i += 1

    return runs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_job(
    path: Path | str,
    blob: VirtualBlob,
    window_size: int = DEFAULT_WINDOW_SIZE,
    blob_config: BlobConfig | None = None,
    *,
    min_match: int = DEFAULT_MIN_MATCH,
) -> TransferJob:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    blob.ensure_loaded()
    cfg = blob_config or BlobConfig(blob.size, blob.seed, blob.path)

    windows: List[TransferWindow] = []
    object_hash = hashlib.sha256()
    total_windows = 0

    blob_data = _blob_bytes(blob, cfg.size)

    for idx, chunk in enumerate(_iter_chunks(source, window_size)):
        total_windows += 1
        object_hash.update(chunk)

        runs = _find_runs_for_chunk(chunk, blob_data, min_match=min_match)
        bref = [
            {"offset": blob_off, "length": run_len, "flags": 0, "at": chunk_off}
            for (chunk_off, blob_off, run_len) in runs
        ]

        proto = encode_proto(chunk, bref if bref else None)

        windows.append(
            TransferWindow(
                idx=idx,
                bref=bref,
                proto=proto,
            )
        )

    if total_windows == 0:
        proto = encode_proto(b"", None)
        windows.append(TransferWindow(idx=0, bref=[], proto=proto))
        total_windows = 1

    return TransferJob(
        object_name=source.name,
        object_size=source.stat().st_size,
        window_size=window_size,
        total_windows=total_windows,
        blob=cfg,
        sha256=object_hash.hexdigest(),
        windows=windows,
    )


def job_to_dict(job: TransferJob) -> Dict[str, object]:
    payload = asdict(job)
    payload["windows"] = [asdict(window) for window in job.windows]
    blob_payload = payload.get("blob")
    if isinstance(blob_payload, dict):
        path_value = blob_payload.get("path")
        if path_value is not None:
            blob_payload["path"] = str(path_value)
    return payload
