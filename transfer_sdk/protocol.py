from __future__ import annotations

import asyncio
import json

from .encoding import TransferJob, job_to_dict
from .serialization import encode_job
from .spool import job_from_dict
from .streaming import reconstruct_window_payload
from .blob import load_blob
from .transport import (
    JOB_CHUNK_BYTES,
    MAX_TEXT_FRAME_BYTES,
    WIRE_VERSION,
    extract_error,
    is_ack_message,
)

_LENGTH_BYTES = 4
_ACK = b"OK"


def _decode(buffer: bytes) -> TransferJob:
    data = json.loads(buffer.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid job payload")
    return job_from_dict(data)


async def send_job(job: TransferJob, host: str, port: int, timeout: float = 30.0) -> None:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    try:
        payload = encode_job(job).encode("utf-8")
        writer.write(len(payload).to_bytes(_LENGTH_BYTES, "big"))
        writer.write(payload)
        await writer.drain()
        ack = await asyncio.wait_for(reader.readexactly(len(_ACK)), timeout=timeout)
        if ack != _ACK:
            raise RuntimeError("unexpected acknowledgement")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# WebSocket transports removed; prefer QUIC/UDP NDJSON or TCP arithmetic receivers.


async def receive_job(reader: asyncio.StreamReader, timeout: float = 30.0) -> TransferJob:
    size_bytes = await asyncio.wait_for(reader.readexactly(_LENGTH_BYTES), timeout=timeout)
    size = int.from_bytes(size_bytes, "big")
    if size <= 0 or size > 256 * 1024 * 1024:
        raise ValueError("invalid job size")
    payload = await asyncio.wait_for(reader.readexactly(size), timeout=timeout)
    return _decode(payload)


def write_ack(writer: asyncio.StreamWriter) -> None:
    writer.write(_ACK)
