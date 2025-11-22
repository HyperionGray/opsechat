from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .transport import CHUNK_FRAME_TYPE, JOB_CHUNK_BYTES, WIRE_VERSION


class ChunkError(Exception):
    """Raised when chunk framing encounters an unrecoverable error."""


class NotChunkFrame(Exception):
    """Raised when a payload does not represent a chunk frame."""


@dataclass(frozen=True)
class ChunkFrame:
    """Single chunk of a larger payload."""

    message_id: str
    index: int
    total: int
    payload: bytes


def _ensure_positive_int(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise ChunkError(f"{field} must be an integer")
    if value < 0:
        raise ChunkError(f"{field} must be non-negative")
    return value


def _decode_chunk_payload(data: Dict[str, object]) -> bytes:
    raw = data.get("payload")
    if not isinstance(raw, str):
        raise ChunkError("chunk payload missing")
    try:
        payload = base64.b64decode(raw.encode("ascii"), validate=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise ChunkError("invalid chunk payload encoding") from exc
    return payload


def decode_chunk_frame(message: str) -> ChunkFrame:
    """Parse a text message into a ChunkFrame, or raise NotChunkFrame."""
    try:
        data = json.loads(message)
    except json.JSONDecodeError as exc:
        raise NotChunkFrame() from exc
    if not isinstance(data, dict):
        raise NotChunkFrame()
    if data.get("wire") != WIRE_VERSION:
        raise NotChunkFrame()
    if data.get("type") != CHUNK_FRAME_TYPE:
        raise NotChunkFrame()

    message_id = str(data.get("id") or "")
    if not message_id:
        raise ChunkError("chunk id missing")

    index = _ensure_positive_int(data.get("index"), "index")
    total = _ensure_positive_int(data.get("total"), "total")
    if total <= 0:
        raise ChunkError("total must be positive")
    if index >= total:
        raise ChunkError("index out of range")

    payload = _decode_chunk_payload(data)
    if not payload and total == 1:
        # allow empty payload when single chunk; multi-chunk empty payloads waste traffic
        pass
    elif not payload:
        raise ChunkError("chunk payload empty")

    return ChunkFrame(message_id=message_id, index=index, total=total, payload=payload)


def encode_chunk_frames(payload: str, chunk_bytes: int = JOB_CHUNK_BYTES) -> List[str]:
    """Encode payload into chunk frames represented as JSON strings."""
    payload_bytes = payload.encode("utf-8")
    if len(payload_bytes) <= chunk_bytes:
        return [payload]

    message_id = uuid.uuid4().hex
    frames: List[str] = []
    total = (len(payload_bytes) + chunk_bytes - 1) // chunk_bytes
    for idx in range(total):
        start = idx * chunk_bytes
        end = start + chunk_bytes
        chunk = payload_bytes[start:end]
        encoded = base64.b64encode(chunk).decode("ascii")
        frame = {
            "wire": WIRE_VERSION,
            "type": CHUNK_FRAME_TYPE,
            "id": message_id,
            "index": idx,
            "total": total,
            "payload": encoded,
        }
        frames.append(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))
    return frames


@dataclass
class _ChunkState:
    total: int
    received: int
    parts: Dict[int, bytes]
    size: int


class ChunkAssembler:
    """Stateful helper that reassembles chunk frames into the original payload."""

    def __init__(self, max_messages: int = 128, max_total_bytes: int = 64 * 1024 * 1024) -> None:
        self._pending: Dict[str, _ChunkState] = {}
        self._max_messages = max_messages
        self._max_total_bytes = max_total_bytes

    def _ensure_capacity(self) -> None:
        if len(self._pending) >= self._max_messages:
            # Drop the oldest entry to make room; deterministic order not crucial.
            key = next(iter(self._pending))
            del self._pending[key]

    def accept(self, message: str) -> Tuple[bool, str | None]:
        """Consume a text message. Returns (is_chunk, payload_text or None).

        When the message is not a chunk frame, returns (False, message).
        When the message is part of a chunk sequence but not yet complete,
        returns (True, None).
        When a chunk sequence completes, returns (True, payload_text).
        Raises ChunkError if the frame is invalid or the sequence is inconsistent.
        """
        try:
            frame = decode_chunk_frame(message)
        except NotChunkFrame:
            return False, message

        state = self._pending.get(frame.message_id)
        if state is None:
            self._ensure_capacity()
            state = _ChunkState(total=frame.total, received=0, parts={}, size=0)
            self._pending[frame.message_id] = state
        elif state.total != frame.total:
            # Reset inconsistent state
            del self._pending[frame.message_id]
            raise ChunkError("chunk sequence total mismatch")

        if frame.index in state.parts:
            raise ChunkError("duplicate chunk index received")

        new_size = state.size + len(frame.payload)
        if new_size > self._max_total_bytes:
            del self._pending[frame.message_id]
            raise ChunkError("chunk sequence exceeds configured limit")

        state.parts[frame.index] = frame.payload
        state.received += 1
        state.size = new_size

        if state.received < state.total:
            return True, None

        assembled: List[bytes] = []
        for idx in range(state.total):
            chunk = state.parts.get(idx)
            if chunk is None:
                del self._pending[frame.message_id]
                raise ChunkError("chunk sequence incomplete")
            assembled.append(chunk)

        del self._pending[frame.message_id]
        payload_bytes = b"".join(assembled)
        try:
            payload_text = payload_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ChunkError("assembled payload is not valid UTF-8") from exc
        return True, payload_text


__all__ = [
    "ChunkAssembler",
    "ChunkError",
    "NotChunkFrame",
    "ChunkFrame",
    "decode_chunk_frame",
    "encode_chunk_frames",
]
