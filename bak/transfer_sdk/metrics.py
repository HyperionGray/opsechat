from __future__ import annotations

import base64
from typing import Dict

from .encoding import TransferJob


def _b64_len_nopad(s: str) -> int:
    """Return number of bytes represented by a URL-safe base64 string without padding."""
    if not s:
        return 0
    pad = (-len(s)) % 4
    if pad:
        s = s + ("=" * pad)
    try:
        return len(base64.urlsafe_b64decode(s.encode("ascii")))
    except Exception:
        # If decoding fails, treat as zero to avoid breaking metrics pages
        return 0


def compute_job_metrics(job: TransferJob) -> Dict[str, float | int | bool]:
    """Compute simple size/ratio metrics for a TransferJob.

    Returns keys:
      - object_bytes: original object size
      - wire_bytes: total bytes of proto payload across all windows
      - compression_ratio: object_bytes / max(wire_bytes, 1)
      - window_count: number of windows
      - chunk_count: alias of window_count (proto chunk granularity not tracked yet)
    """
    object_bytes = int(getattr(job, "object_size", 0) or 0)
    window_count = int(getattr(job, "total_windows", 0) or len(job.windows))

    wire_bytes = 0
    encoded_proto_bytes = 0
    windows_with_proto = 0
    for w in getattr(job, "windows", []) or []:
        proto = getattr(w, "proto", None)
        if isinstance(proto, str) and proto:
            windows_with_proto += 1
            # decoded (actual proto bytes)
            wire_bytes += _b64_len_nopad(proto)
            # encoded characters length (what ends up inside JSON before quotes)
            encoded_proto_bytes += len(proto)

    if wire_bytes <= 0:
        # Avoid div-by-zero; return neutral metrics when no proto present
        ratio = 1.0
    else:
        ratio = (object_bytes / wire_bytes) if object_bytes > 0 else 1.0

    # Base64 overhead from encoding the proto payloads (excludes JSON envelope overhead)
    b64_overhead_bytes = max(encoded_proto_bytes - wire_bytes, 0)
    avg_window_wire_bytes = (wire_bytes / window_count) if window_count > 0 else 0.0
    expanded = bool(wire_bytes > 0 and object_bytes > 0 and ratio <= 1.0)

    return {
        "object_bytes": object_bytes,
        "wire_bytes": wire_bytes,
        "compression_ratio": ratio,
        "window_count": window_count,
        "chunk_count": window_count,
        # extended diagnostics
        "encoded_proto_bytes": encoded_proto_bytes,
        "b64_overhead_bytes": b64_overhead_bytes,
        "avg_window_wire_bytes": avg_window_wire_bytes,
        "windows_with_proto": windows_with_proto,
        "expanded": expanded,
    }


__all__ = ["compute_job_metrics"]
