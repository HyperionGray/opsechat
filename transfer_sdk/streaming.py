from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Optional

from .blob import VirtualBlob, load_blob
from .arithmetic import decode_proto, encode_proto
from .config import DEFAULT_WINDOW_SIZE, BlobConfig, DEFAULT_MIN_MATCH
from .encoding import TransferWindow, _blob_bytes, _find_runs_for_chunk

__all__ = [
    "iter_upload_file_chunks",
    "iter_request_body_chunks",
    "StreamJob",
    "StreamWindow",
    "WINDOW_SENTINEL",
    "iter_windows",
    "stream_file_to_queue",
    "consume_window_queue",
    "reconstruct_window_payload",
]
async def _maybe_await(result: Awaitable[None] | None) -> None:
    if result is None:
        return
    await result


def iter_upload_file_chunks(upload: Any, chunk_size: int) -> AsyncIterator[bytes]:
    """Yield upload chunks from a FastAPI-style UploadFile or compatible object."""

    async def iterator() -> AsyncIterator[bytes]:
        try:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(upload, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result  # type: ignore[arg-type]

    return iterator()


def iter_request_body_chunks(request: Any) -> AsyncIterator[bytes]:
    """Yield raw body chunks from a FastAPI Request or compatible object."""

    async def iterator() -> AsyncIterator[bytes]:
        async for chunk in request.stream():
            if chunk:
                yield chunk

    return iterator()


@dataclass(frozen=True)
class StreamJob:
    """Metadata describing a streaming transfer job."""

    path: Path
    window_size: int = DEFAULT_WINDOW_SIZE
    blob_size: int = 1 * 1024 * 1024 * 1024  # 1 GiB default blob
    blob_seed: int = 1337

    def load_blob(self) -> VirtualBlob:
        return load_blob(BlobConfig(size=self.blob_size, seed=self.blob_seed))


@dataclass(frozen=True)
class StreamWindow:
    """Single streaming window with arithmetic encoding."""

    idx: int
    length: int
    bref: list[dict[str, int]]
    proto: str
    digest: str

    def to_transfer_window(self) -> TransferWindow:
        """Convert to the TransferWindow structure used by job JSON."""
        return TransferWindow(idx=self.idx, bref=self.bref, proto=self.proto)


# Sentinel placed on queues to signal end-of-stream.
WINDOW_SENTINEL: StreamWindow | None = None


def iter_windows(path: Path, blob: VirtualBlob, window_size: int = DEFAULT_WINDOW_SIZE) -> Iterable[StreamWindow]:
    """Yield StreamWindow objects for *path* without buffering the full job."""
    blob.ensure_loaded()
    produced = False
    blob_data = _blob_bytes(blob, getattr(blob, "size", None))
    for idx, chunk in enumerate(_iter_chunks(path, window_size)):
        produced = True
        digest = hashlib.sha256(chunk).hexdigest()
        runs = _find_runs_for_chunk(chunk, blob_data, min_match=DEFAULT_MIN_MATCH)
        bref = [
            {"offset": boff, "length": blen, "flags": 0, "at": coff}
            for (coff, boff, blen) in runs
        ]
        proto = encode_proto(chunk, bref if bref else None)
        yield StreamWindow(
            idx=idx,
            length=len(chunk),
            bref=bref,
            proto=proto,
            digest=digest,
        )

    if not produced:
        digest = hashlib.sha256(b"").hexdigest()
        proto = encode_proto(b"", None)
        yield StreamWindow(idx=0, length=0, bref=[], proto=proto, digest=digest)


async def stream_file_to_queue(job: StreamJob, queue: asyncio.Queue[StreamWindow | None]) -> None:
    """Stream windows for *job* into the supplied asyncio queue.
    """
    blob = job.load_blob()
    blob.ensure_loaded()

    for window in iter_windows(job.path, blob, window_size=job.window_size):
        await queue.put(window)
    await queue.put(WINDOW_SENTINEL)


async def consume_window_queue(
    queue: asyncio.Queue[StreamWindow | None],
    blob: VirtualBlob,
    *,
    sample_every: int = 10,
    on_window: Optional[Callable[[StreamWindow], Awaitable[None] | None]] = None,
) -> dict[str, int | float]:
    """Consume windows from *queue*, performing integrity checks on sampled entries.

    Returns statistics describing the run (windows processed, sampled, failures).
    """
    blob.ensure_loaded()

    processed = 0
    sampled = 0
    failures = 0

    while True:
        window = await queue.get()
        if window is WINDOW_SENTINEL:
            queue.task_done()
            break
        assert window is not None
        processed += 1

        should_sample = sample_every > 0 and (window.idx % sample_every == 0 or window.idx == 0)
        if should_sample:
            sampled += 1
            payload = reconstruct_window_payload(window.to_transfer_window(), blob, window.length)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != window.digest:
                failures += 1

        if on_window is not None:
            await _maybe_await(on_window(window))

        queue.task_done()

    return {
        "windows": processed,
        "sampled": sampled,
        "failures": failures,
        "failure_rate": (failures / sampled) if sampled else 0.0,
    }


def reconstruct_window_payload(window: TransferWindow | dict, blob: VirtualBlob, length: int) -> bytes:
    """Rebuild the original payload for *window* using *blob*.

    Accepts either a TransferWindow dataclass or a plain dict as found in
    serialized manifests to be resilient in API contexts.
    """
    if isinstance(window, dict):
        proto = window.get("proto")
        if proto:
            return decode_proto(proto, blob, length)
        bref_list = window.get("bref") or []
    else:
        proto = getattr(window, "proto", None)
        if proto:
            return decode_proto(proto, blob, length)
        if getattr(window, "raw", None) is not None:
            raise ValueError("raw window payloads are unsupported; expected proto encoding")
        bref_list = getattr(window, "bref", [])

    if not bref_list:
        return b""

    buffer = bytearray(b"\x00" * length)
    for ref in sorted(bref_list, key=lambda r: int(r.get("at", 0))):
        offset = int(ref.get("offset", 0))
        ref_length = int(ref.get("length", 0))
        at = int(ref.get("at", 0))
        if ref_length <= 0 or at >= length:
            continue
        take = min(ref_length, max(0, length - at))
        if take <= 0:
            continue
        buffer[at : at + take] = blob.read(offset, take)
    return bytes(buffer)


def _iter_chunks(path: Path, window_size: int) -> Iterable[bytes]:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(window_size)
            if not chunk:
                break
            yield chunk
