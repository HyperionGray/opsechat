from __future__ import annotations

import hashlib

MAX_TEXT_FRAME_BYTES = 256 * 1024  # 256 KiB default frame size
JOB_CHUNK_BYTES = 120 * 1024  # target chunk size when splitting large payloads
WIRE_VERSION = "transfer-sdk.v1"
CHUNK_FRAME_TYPE = "job-chunk"
ACK_MESSAGE = "ACK"
ERROR_PREFIX = "ERROR:"


def is_ack_message(message: str) -> bool:
    """Return True if the message represents a standard ACK."""
    return message.strip().upper() == ACK_MESSAGE


def build_ack() -> str:
    """Return the canonical acknowledgement string."""
    return ACK_MESSAGE


def build_error(reason: str) -> str:
    """Format an error frame for WebSocket/text transports."""
    detail = (reason or "unknown error").strip()
    if detail.upper().startswith(ERROR_PREFIX):
        return detail
    return f"{ERROR_PREFIX} {detail}"


def extract_error(message: str) -> str | None:
    """Extract the error portion of a frame if it matches the error prefix."""
    if not message.startswith(ERROR_PREFIX):
        return None
    return message[len(ERROR_PREFIX) :].strip()


def compute_checksum(payload: bytes, algorithm: str = "sha256") -> str:
    """Compute a hex digest for payload integrity checks."""
    try:
        digest = hashlib.new(algorithm)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"unsupported checksum algorithm: {algorithm}") from exc
    digest.update(payload)
    return digest.hexdigest()


__all__ = [
    "MAX_TEXT_FRAME_BYTES",
    "JOB_CHUNK_BYTES",
    "WIRE_VERSION",
    "CHUNK_FRAME_TYPE",
    "ACK_MESSAGE",
    "ERROR_PREFIX",
    "is_ack_message",
    "build_ack",
    "build_error",
    "extract_error",
    "compute_checksum",
]
