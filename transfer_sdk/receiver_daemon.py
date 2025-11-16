from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .blob import VirtualBlob, load_blob
from .encoding import TransferJob, TransferWindow, job_to_dict
from .protocol import receive_job, write_ack
from .arithmetic import decode_proto


def _reconstruct_from_bref(window: TransferWindow, blob: VirtualBlob, window_size: int) -> bytes:
    """Rebuild a window using its bref entries (best-effort fallback)."""
    buf = bytearray(b"\x00" * window_size)
    for ref in sorted(window.bref or [], key=lambda r: int(r.get("at", 0))):
        offset = int(ref.get("offset", 0))
        length = int(ref.get("length", 0))
        at = int(ref.get("at", 0))
        if length <= 0 or at >= window_size:
            continue
        take = min(length, max(0, window_size - at))
        if take <= 0:
            continue
        segment = blob.read(offset, take)
        buf[at : at + take] = segment
    return bytes(buf)


def reconstruct(job: TransferJob, output_dir: Path) -> Path:
    """Eager reconstruction path (legacy). Writes full payload to disk.

    Retained for compatibility but no longer the default; windowed mode avoids
    materializing the entire file to preserve space savings of proto+bref.
    """
    blob = load_blob(job.blob)
    blob.ensure_loaded()
    buffer = bytearray()
    for window in job.windows:
        proto = getattr(window, "proto", None)
        if proto:
            data = decode_proto(proto, blob, job.window_size)
        elif window.bref:
            data = _reconstruct_from_bref(window, blob, job.window_size)
        elif window.raw is not None:
            raise ValueError("raw window payloads are unsupported; expected proto encoding")
        else:
            data = b""
        buffer.extend(data)
    payload = bytes(buffer[: job.object_size])
    digest = hashlib.sha256(payload).hexdigest()
    if digest != job.sha256:
        raise ValueError("sha256 mismatch during reconstruction")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / job.object_name
    with tempfile.NamedTemporaryFile("wb", dir=str(output_dir), delete=False) as tmp:
        tmp.write(payload)
        temp_path = Path(tmp.name)
    temp_path.replace(target)
    return target


def persist_windows_manifest(job: TransferJob, output_dir: Path) -> Path:
    """Persist only the windowed representation (proto + bref) as a manifest.

    Creates <object_name>.ff3job JSON file containing job metadata and windows.
    This preserves compression/time savings and defers full reconstruction to
    future on-demand reads (e.g. virtual file system layer).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = job_to_dict(job)
    manifest["virtual"] = True
    manifest_path = output_dir / f"{job.object_name}.ff3job"
    with tempfile.NamedTemporaryFile("w", dir=str(output_dir), delete=False) as tmp:
        json.dump(manifest, tmp, separators=(",", ":"))
        temp_path = Path(tmp.name)
    temp_path.replace(manifest_path)
    return manifest_path


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, output_dir: Path) -> None:
    peer = writer.get_extra_info("peername")
    try:
        job = await receive_job(reader)
        mode = os.environ.get("FF3_RECEIVER_MODE", "windowed").lower()
        if mode == "reconstruct":
            path = reconstruct(job, output_dir)
            print(f"[receiver] reconstructed {path.name} ({job.total_windows} windows) mode=reconstruct")
        else:
            path = persist_windows_manifest(job, output_dir)
            print(f"[receiver] stored manifest {path.name} ({job.total_windows} windows) mode=windowed")
        write_ack(writer)
        await writer.drain()
    except Exception as exc:
        print(f"[receiver] error from {peer}: {exc}")
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def run_server(bind: str, port: int, output_dir: Path) -> None:
    server = await asyncio.start_server(lambda r, w: handle_client(r, w, output_dir), host=bind, port=port)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[receiver] listening on {addresses}")
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Receiver daemon: accept arithmetic transfers and reconstruct files")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9350, help="TCP port")
    parser.add_argument("--output", type=Path, required=True, help="Directory to write reconstructed files")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(run_server(args.bind, args.port, args.output))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
