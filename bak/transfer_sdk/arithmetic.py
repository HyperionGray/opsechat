
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

# Public API expected by the rest of the SDK:
#   - encode_proto(window_bytes: bytes, hint: object) -> str
#   - decode_proto(proto: str, blob, window_size: int) -> bytes
#
# "hint" may be:
#   - None:           no references; window will be emitted as a single LIT
#   - anchor-like:    object with .offset and .length (legacy)
#   - run list:       list of dicts with {"offset": int, "length": int, "at": int?, "flags": int?}
#
# The returned string is URL-safe base64 of a compact binary proto using an
# IPROG/PVRT layout (v1) with varint-coded fields. This first version focuses on
# COPY/LIT. A follow-on version will add mod-256 delta (ADDB) while preserving the
# v1 envelope.

MAGIC = b"IPV1"  # IPROG/PVRT v1
OP_LIT  = 0x00   # LIT  <len:varint> <bytes>
OP_CPYI = 0x01   # COPY from PVRT index: <idx:varint>
OP_END  = 0x7F   # explicit end-of-stream (optional; decoder also checks window_size)


# ------------------ Varint helpers (LEB128, unsigned + zigzag) ------------------

def _uvarint_encode(n: int) -> bytes:
    if n < 0:
        raise ValueError("uvarint must be non-negative")
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(0x80 | b)
        else:
            out.append(b)
            break
    return bytes(out)

def _uvarint_decode(buf: memoryview, pos: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
        if shift > 63:
            raise ValueError("varint overflow")
    return result, pos

def _zigzag(n: int) -> int:
    return (n << 1) ^ (n >> 63)

def _unzigzag(z: int) -> int:
    return (z >> 1) ^ -(z & 1)


# ------------------ Core IPROG/PVRT encoder ------------------

@dataclass(frozen=True)
class _Run:
    at: int
    offset: int
    length: int

def _normalize_hint(hint, window_len: int) -> List[_Run]:
    """Coerce hint (None | anchor | run-list) into a sorted, non-overlapping run list.

    Any spans outside [0, window_len) are clamped; zero-length entries are dropped.
    """
    runs: List[_Run] = []
    if hint is None:
        return runs

    # anchor-like object: has `.offset` and `.length`
    if hasattr(hint, "offset") and hasattr(hint, "length"):
        off = int(getattr(hint, "offset"))
        ln  = int(getattr(hint, "length"))
        ln  = max(0, min(ln, window_len))  # clamp
        if ln > 0:
            runs.append(_Run(at=0, offset=off, length=ln))
        return runs

    # list of dicts: each item may carry at/offset/length
    if isinstance(hint, (list, tuple)):
        for ref in hint:
            if not isinstance(ref, dict):
                continue
            off = int(ref.get("offset", 0))
            ln  = int(ref.get("length", 0))
            at  = int(ref.get("at", 0))
            if ln <= 0:
                continue
            if at >= window_len:
                continue
            if at < 0:
                # clamp negative at to 0 by trimming from the left
                trim = -at
                at = 0
                if ln > trim:
                    ln -= trim
                    off += trim
                else:
                    continue
            if at + ln > window_len:
                ln = window_len - at
            if ln > 0:
                runs.append(_Run(at=at, offset=off, length=ln))

    # Merge & sort by 'at'; coalesce contiguous entries with same blob alignment
    runs.sort(key=lambda r: (r.at, r.offset))
    merged: List[_Run] = []
    for r in runs:
        if not merged:
            merged.append(r); continue
        m = merged[-1]
        if (m.at + m.length == r.at) and (m.offset + m.length == r.offset):
            merged[-1] = _Run(at=m.at, offset=m.offset, length=m.length + r.length)
        else:
            merged.append(r)
    return merged

def _build_pvrt(runs: Sequence[_Run]) -> Tuple[List[Tuple[int,int]], dict[Tuple[int,int], int]]:
    """Return PVRT as unique (offset,length) entries and a map -> index."""
    uniq: List[Tuple[int,int]] = []
    idx: dict[Tuple[int,int], int] = {}
    for r in runs:
        key = (r.offset, r.length)
        if key in idx:
            continue
        idx[key] = len(uniq)
        uniq.append(key)
    return uniq, idx

def encode_proto(window: bytes, hint=None) -> str:
    """Encode a single window using IPROG/PVRT v1.

    - Builds a PVRT from the provided runs (or a single anchor).
    - Emits an instruction stream (LIT, CPYI) that reconstructs the window.
    - Returns URL-safe base64 of the binary proto.

    This v1 stream uses varints and raw bytes (no arithmetic coder yet) to keep
    the first drop-in simple. A follow-up v2 will add mod-256 delta (ADDB) and
    arithmetic coding for opcodes and small fields without changing the outer
    contract.
    """
    n = len(window)
    runs = _normalize_hint(hint, n)
    pvrt, pvrt_index = _build_pvrt(runs)

    out = bytearray()
    out.extend(MAGIC)
    # PVRT count
    out.extend(_uvarint_encode(len(pvrt)))
    # PVRT entries
    for off, ln in pvrt:
        out.extend(_uvarint_encode(off))
        out.extend(_uvarint_encode(ln))

    # Emit IPROG in order of appearance in the window
    pos = 0
    for r in sorted(runs, key=lambda x: x.at):
        if r.at > pos:
            # literal gap
            gap = window[pos:r.at]
            out.append(OP_LIT)
            out.extend(_uvarint_encode(len(gap)))
            out.extend(gap)
            pos = r.at
        # copy PVRT entry
        out.append(OP_CPYI)
        out.extend(_uvarint_encode(pvrt_index[(r.offset, r.length)]))
        pos += r.length

    if pos < n:
        tail = window[pos:]
        out.append(OP_LIT)
        out.extend(_uvarint_encode(len(tail)))
        out.extend(tail)
        pos = n

    out.append(OP_END)
    # Return URL-safe base64 (strip padding for compactness)
    b64 = base64.urlsafe_b64encode(bytes(out)).decode("ascii").rstrip("=")
    return b64


# ------------------ Decoder ------------------

def _b64_decode_nopad(s: str) -> bytes:
    # restore padding
    pad = (-len(s)) % 4
    if pad:
        s = s + ("=" * pad)
    return base64.urlsafe_b64decode(s.encode("ascii"))

def decode_proto(proto: str, blob, window_size: int) -> bytes:
    """Decode PVRT/IPROG v1 into a window.

    - `blob` exposes read(offset:int, length:int) -> bytes.
    - `window_size` is used as a guard; we stop after producing this many bytes.
    """
    buf = memoryview(_b64_decode_nopad(proto))
    pos = 0

    # Header
    if len(buf) < 4 or bytes(buf[:4]) != MAGIC:
        raise ValueError("bad proto magic")
    pos = 4

    # PVRT table
    pvrt_count, pos = _uvarint_decode(buf, pos)
    pvrt: List[Tuple[int,int]] = []
    for _ in range(pvrt_count):
        off, pos = _uvarint_decode(buf, pos)
        ln, pos  = _uvarint_decode(buf, pos)
        pvrt.append((off, ln))

    # IPROG
    out = bytearray()
    while pos < len(buf) and len(out) < window_size:
        op = buf[pos]; pos += 1
        if op == OP_END:
            break
        if op == OP_LIT:
            ln, pos = _uvarint_decode(buf, pos)
            if ln:
                if pos + ln > len(buf):
                    raise ValueError("truncated LIT")
                out.extend(buf[pos:pos+ln])
                pos += ln
            continue
        if op == OP_CPYI:
            idx, pos2 = _uvarint_decode(buf, pos)
            pos = pos2
            if idx < 0 or idx >= len(pvrt):
                raise ValueError("pvrt index out of range")
            off, ln = pvrt[idx]
            if ln:
                seg = blob.read(off, ln)
                out.extend(seg)
            continue
        raise ValueError(f"unknown opcode {op:#x}")

    # Guard/truncate to the expected window size
    if len(out) > window_size:
        out = out[:window_size]
    elif len(out) < window_size:
        # Incomplete stream; pad with zeros to preserve window size invariant
        # (protocol receivers depend on fixed window boundaries)
        out.extend(b"\x00" * (window_size - len(out)))
    return bytes(out)
