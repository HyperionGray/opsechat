from __future__ import annotations

"""
Adaptive sender with transport fallback:
  1) QUIC (NDJSON) primary
  2) UDP (NDJSON) after 3rd QUIC failure
  3) TCP arithmetic (TransferJob over TCP) final fallback

On success, prints the transport used. On failure, exits non-zero.

Env defaults:
  FF3_QUIC_ADDR=127.0.0.1 FF3_QUIC_PORT=41002
  FF3_UDP_ADDR=127.0.0.1  FF3_UDP_PORT=41003
  FF3_TCP_ARITH_ADDR=127.0.0.1 FF3_TCP_ARITH_PORT=9350  (receiver_daemon)

Usage:
  python -m tools.send_auto <file> [--user user] [--name dest_name]

Note: For QUIC/UDP, if no PVRT manifest is provided, we send a RAW frame only when
      FF3_QUIC_ALLOW_RAW/FF3_UDP_ALLOW_RAW is enabled on the server. Otherwise
      we send empty BREF which is useful for protocol plumbing but not data.
      For robust high-ratio transfer, prefer providing a BREF JSON manifest
      or rely on the TCP arithmetic fallback which sends a full TransferJob.
"""

import argparse
import asyncio
import os
from pathlib import Path
import json

import httpx

from transfer_sdk.config import TransferSettings
from transfer_sdk.upload_manager import TransferIngestor
from transfer_sdk.protocol import send_job


async def try_quic(path: Path, *, user: str, name: str, attempts: int = 3) -> bool:
    from tools.quic_send import send_quic_bytes
    host = os.environ.get("FF3_QUIC_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_QUIC_PORT", "41002"))
    payload = path.read_bytes()
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            await send_quic_bytes(host, port, payload, name=name, user=user)
            print(f"[send-auto] QUIC success on attempt {i}")
            return True
        except Exception as exc:
            last_err = exc
            await asyncio.sleep(0.05 * i)
    if last_err:
        print(f"[send-auto] QUIC failed after {attempts} attempts: {last_err}")
    return False


async def try_udp(path: Path, *, user: str, name: str) -> bool:
    from tools.udp_send import send_udp_bytes
    host = os.environ.get("FF3_UDP_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_UDP_PORT", "41003"))
    payload = path.read_bytes()
    try:
        resp = await send_udp_bytes(host, port, payload, name=name, user=user)
        if resp and resp.upper().startswith("OK"):
            print("[send-auto] UDP success")
            return True
        # Accept empty or non-OK responses as failure
        print(f"[send-auto] UDP response: {resp!r}")
        return False
    except Exception as exc:
        print(f"[send-auto] UDP failed: {exc}")
        return False


async def try_tcp_arith(path: Path, *, user: str, name: str) -> bool:
    host = os.environ.get("FF3_TCP_ARITH_ADDR", "127.0.0.1")
    port = int(os.environ.get("FF3_TCP_ARITH_PORT", "9350"))
    # Build arithmetic job using local blob; send over protocol
    settings = TransferSettings.from_env()
    settings.ensure_directories()
    ingestor = TransferIngestor(settings)
    ingestor.ensure_ready()
    result = ingestor.build_job_for_path(path)
    job = result.job
    # Override user/name in job metadata (object_name)
    # The receiver will store <object_name>.ff3job (or reconstruct if configured)
    job.object_name = name
    try:
        await send_job(job, host, port, timeout=60.0)
        print("[send-auto] TCP arithmetic success")
        return True
    except Exception as exc:
        print(f"[send-auto] TCP arithmetic failed: {exc}")
        return False


async def send_with_fallbacks(
    path: Path,
    *,
    user: str,
    name: str,
    quic_attempts: int = 3,
) -> str | None:
    """Attempt transports in priority order. Returns the transport label on success."""
    if await try_quic(path, user=user, name=name, attempts=quic_attempts):
        return "quic"
    if await try_udp(path, user=user, name=name):
        return "udp"
    if await try_tcp_arith(path, user=user, name=name):
        return "tcp"
    return None


def main():
    p = argparse.ArgumentParser(description="Adaptive sender with QUIC→UDP→TCP fallbacks")
    p.add_argument("path", type=Path, help="File to send")
    p.add_argument("--user", default=os.environ.get("FF3_USER", "user"))
    p.add_argument("--name", default=None, help="Destination leaf name (defaults to source filename)")
    p.add_argument("--no-register", action="store_true", help="Disable integrity auto-register with local sender daemon")
    args = p.parse_args()

    src = args.path
    if not src.is_file():
        raise SystemExit(f"file not found: {src}")
    name = args.name or src.name

    async def _auto_register(src: Path):
        if args.no_register:
            return
        url = os.environ.get("FF3_SENDER_INTEGRITY_URL", "http://127.0.0.1:9352")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.post(f"{url}/register", json={"path": str(src)})
                if r.status_code == 200:
                    data = r.json()
                    sha = data.get("sha256")
                    if sha:
                        print(f"[send-auto] registered {src.name} sha256={sha[:12]}...")
        except Exception:
            # Best-effort: ignore failures
            pass

    async def _run():
        await _auto_register(src)
        result = await send_with_fallbacks(src, user=args.user, name=name)
        return 0 if result else 1

    rc = asyncio.run(_run())
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
