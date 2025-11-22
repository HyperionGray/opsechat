"""ff3sync: rsync-like high-efficiency file transfer using FastFiles3 arithmetic encoding.

Transport note: WebSocket transport has been removed. This CLI now uses the
TCP arithmetic receiver daemon (transfer_sdk.receiver_daemon) over a direct
TCP connection. For remote hosts, it bootstraps the receiver via SSH and binds
to the given port, then streams a TransferJob over TCP.
"""
from __future__ import annotations

import argparse
import os
import random
import shlex
import string
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from .config import TransferSettings
from .upload_manager import TransferIngestor
from .spool import write_job_to_spool
from .protocol import send_job
from .blob import load_blob


def _rand_token(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _ssh(remote: str, command: str, timeout: int = 20) -> subprocess.CompletedProcess:
    wrapped = ["ssh", remote, command]
    return subprocess.run(wrapped, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, text=True)


def _start_remote_receiver(remote: str, out_dir: str, port: int) -> None:
    # Start arithmetic TCP receiver on remote host writing manifests to out_dir
    cmd = (
        f"python -m transfer_sdk.receiver_daemon --bind 127.0.0.1 --port {port} --output {shlex.quote(out_dir)}"
    )
    full = f"nohup {cmd} >/dev/null 2>&1 &"
    res = _ssh(remote, full)
    if res.returncode != 0:
        raise RuntimeError(f"remote start failed: {res.stderr.strip()}")


def _wait_remote_ready(remote: str, port: int, attempts: int = 40) -> None:
    # Poll remote process list for listening socket on the specified port
    # Note: requires 'ss' or 'netstat' to be available on remote.
    check_cmd = shlex.quote(
        f"(ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep ':{port} ' || true"
    )
    for _ in range(attempts):
        res = _ssh(remote, check_cmd)
        if res.returncode == 0 and res.stdout.strip():
            return
        time.sleep(0.25)
    raise RuntimeError("remote receiver not ready")


def push(local_path: Path, remote: str, remote_out: str, port: int, window_size: int) -> None:
    settings = TransferSettings.from_env()
    # Use a temporary spool for single job
    settings.ensure_directories()
    ingestor = TransferIngestor(settings)
    ingestor.ensure_ready()
    if not local_path.exists():
        raise SystemExit("source file does not exist")
    # Build job directly
    result = ingestor.build_job_for_path(local_path)
    job = result.job
    write_job_to_spool(job, settings.spool_dir)
    # Start remote TCP receiver daemon and wait until it's listening
    _start_remote_receiver(remote, remote_out, port)
    _wait_remote_ready(remote, port)
    t0 = time.time()
    # Stream job
    try:
        import asyncio
        host = remote.split('@')[-1]
        asyncio.run(send_job(job, host, port, timeout=60.0))
    except Exception as exc:
        raise SystemExit(f"transfer failed: {exc}")
    elapsed = time.time() - t0
    # Compute simple ratio stats
    blob = load_blob(job.blob)
    blob.ensure_loaded()
    ratio = job.object_size / max(1, job.window_size * job.total_windows)  # coarse
    print(f"[ff3sync] sent {job.object_name} size={job.object_size} windows={job.total_windows} elapsed={elapsed:.2f}s ratio~{ratio:.2f}")


def parse_remote(spec: str) -> tuple[str, str]:
    # user@host:/path style
    if ":" not in spec:
        raise ValueError("remote spec must be user@host:/path")
    host_part, path_part = spec.split(":", 1)
    return host_part, path_part or "/tmp/ff3sync-remote"


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="ff3sync", description="High-ratio file transfer over TCP arithmetic receiver.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_push = sub.add_parser("push", help="Push local file to remote target")
    p_push.add_argument("source", type=Path)
    p_push.add_argument("target", type=str, help="remote spec user@host:/path/out")
    p_push.add_argument("--port", type=int, default=9350)
    p_push.add_argument("--window-size", type=int, default=64*1024, help="Override window size (experimental)")

    # Placeholder for future 'pull'
    p_pull = sub.add_parser("pull", help="Pull remote file to local path (NYI)")
    p_pull.add_argument("remote", type=str)
    p_pull.add_argument("local", type=Path)

    args = parser.parse_args(argv)
    if args.command == "push":
        remote, remote_out = parse_remote(args.target)
        push(args.source, remote, remote_out, args.port, args.window_size)
    elif args.command == "pull":
        raise SystemExit("pull not implemented yet")
    else:
        parser.error("unknown command")


if __name__ == "__main__":  # pragma: no cover
    main()
