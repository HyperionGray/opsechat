"""Minimal building blocks for PacketFS-style transfers.

The modules exposed here are intentionally small and synchronous to make
experimentation easy. High-level helpers:

- load_blob() – create the shared virtual blob
- build_job() – convert a file into PVRT/IPROG style windows
- send_job()/receive_job() – wire protocol helpers
"""

from .blob import VirtualBlob, load_blob
from .config import DEFAULT_WINDOW_SIZE, DEFAULT_BLOB_SIZE, DEFAULT_BLOB_SEED, TransferSettings
from .encoding import build_job
from .arithmetic import encode_proto, decode_proto
from .framing import (
    ChunkAssembler,
    ChunkError,
    NotChunkFrame,
    decode_chunk_frame,
    encode_chunk_frames,
)
from .protocol import send_job, receive_job
from .serialization import (
    JobPayload,
    JobValidationError,
    decode_job_message,
    encode_job,
)
from .streaming import (
    StreamJob,
    StreamWindow,
    WINDOW_SENTINEL,
    consume_window_queue,
    iter_windows,
    reconstruct_window_payload,
    stream_file_to_queue,
)
from .spool import write_job_to_spool, load_job_from_spool, iter_spool_jobs, job_from_dict
from .streaming import iter_request_body_chunks, iter_upload_file_chunks
from .transport import (
    ACK_MESSAGE,
    ERROR_PREFIX,
    MAX_TEXT_FRAME_BYTES,
    JOB_CHUNK_BYTES,
    WIRE_VERSION,
    CHUNK_FRAME_TYPE,
    build_ack,
    build_error,
    compute_checksum,
    extract_error,
    is_ack_message,
)
from .upload_manager import TransferIngestor
# WebSocket transport removed; no TransferHub/dispatch_job/receive_text exports.

__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_BLOB_SIZE",
    "DEFAULT_BLOB_SEED",
    "TransferSettings",
    "TransferIngestor",
    "VirtualBlob",
    "load_blob",
    "build_job",
    "send_job",
    "receive_job",
    "encode_proto",
    "decode_proto",
    "encode_chunk_frames",
    "decode_chunk_frame",
    "ChunkAssembler",
    "ChunkError",
    "NotChunkFrame",
    "encode_job",
    "decode_job_message",
    "JobPayload",
    "JobValidationError",
    "write_job_to_spool",
    "load_job_from_spool",
    "iter_spool_jobs",
    "job_from_dict",
    "iter_upload_file_chunks",
    "iter_request_body_chunks",
    "StreamJob",
    "StreamWindow",
    "iter_windows",
    "stream_file_to_queue",
    "consume_window_queue",
    "reconstruct_window_payload",
    "WINDOW_SENTINEL",
    "ACK_MESSAGE",
    "ERROR_PREFIX",
    "MAX_TEXT_FRAME_BYTES",
    "JOB_CHUNK_BYTES",
    "WIRE_VERSION",
    "CHUNK_FRAME_TYPE",
    "build_ack",
    "build_error",
    "is_ack_message",
    "extract_error",
    "compute_checksum",
]
